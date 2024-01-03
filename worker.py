import os
import sys
import signal
import argparse
import requests
from urllib.parse import urljoin
from socket import gethostname
from io import BytesIO
from zipfile import ZipFile
from shutil import move, rmtree
from uuid import uuid4
from time import time, sleep
from subprocess import Popen, check_output, STDOUT, CalledProcessError

from fame.core import fame_init
from fame.core.module import ModuleInfo
from fame.core.internals import Internals
from fame.common.config import fame_config
from fame.common.constants import MODULES_ROOT
from fame.common.pip import pip_install
from fame.common.cleaner import get_old_analyses, get_old_disabled_users


UNIX_INSTALL_SCRIPTS = {
    "install.sh": ["sh", "{}"],
    "install.py": ["python", "{}"]
}

WIN_INSTALL_SCRIPTS = {
    "install.cmd": ["{}"],
    "install.py": ["python", "{}"]
}


class Worker:
    def __init__(self, queues, celery_args, refresh_interval):
        self.queues = list(set(queues))
        self.celery_args = [arg for arg in celery_args.split(' ') if arg]
        self.refresh_interval = refresh_interval

    def update_modules(self):
        # Module updates are only needed for remote workers
        if fame_config.remote:
            # First, backup current code
            backup_path = os.path.join(fame_config.temp_path, 'modules_backup_{}'.format(uuid4()))
            os.makedirs(backup_path, exist_ok=True)
            for module in os.listdir(MODULES_ROOT):
                move(os.path.join(MODULES_ROOT, module), backup_path)

            # Replace current code with code fetched from web server
            url = urljoin(fame_config.remote, '/modules/download')
            try:
                response = requests.get(url, stream=True, headers={'X-API-KEY': fame_config.api_key})
                response.raise_for_status()

                with ZipFile(BytesIO(response.content), 'r') as zipf:
                    zipf.extractall(MODULES_ROOT)

                rmtree(backup_path)
                print("Updated modules.")
            except Exception as e:
                print(("Could not update modules: '{}'".format(e)))
                print("Restoring previous version")
                move(backup_path, MODULES_ROOT)

        self.update_module_requirements()

    def update_module_requirements(self):
        installed = []
        for module in ModuleInfo.get_collection().find():
            module = ModuleInfo(module)

            if 'error' in module:
                del(module['error'])

            if module['type'] == "Processing":
                should_update = (module['queue'] in self.queues)
            elif module['type'] in ["Threat Intelligence", "Reporting", "Filetype"]:
                should_update = True
            else:
                should_update = (not fame_config.remote)

            if should_update:
                installed += self.update_python_requirements(module, installed)
                installed += self.launch_install_scripts(module, installed)

            module.save()

    def update_python_requirements(self, module, already_installed):
        requirements = self._module_requirements(module)

        if requirements and not requirements in already_installed:
            print(("Installing requirements for '{}' ({})".format(module['name'], requirements)))

            rcode, output = pip_install('-r', requirements)

            # In case pip failed
            if rcode:
                self._module_installation_error(requirements, module, output.decode('utf-8', errors='replace'))
        return [requirements]

    def launch_install_scripts(self, module, already_installed):
        scripts = self._module_install_scripts(module)

        for script in scripts:
            if script in already_installed:
                continue
            try:
                print(("Launching installation script '{}'".format(' '.join(script))))
                check_output(script, stderr=STDOUT)
            except CalledProcessError as e:
                self._module_installation_error(' '.join(script), module, e.output.decode('utf-8', errors='replace'))
            except Exception as e:
                self._module_installation_error(' '.join(script), module, e)
        return scripts

    def _module_installation_error(self, cmd, module, errors):
        errors = "{}: error on '{}':\n\n{}".format(cmd, gethostname(), errors)

        module['enabled'] = False
        module['error'] = errors

        print(errors)

    def _module_requirements(self, module):
        return module.get_file('requirements.txt')

    def _module_install_scripts(self, module):
        results = []

        if sys.platform == "win32":
            INSTALL_SCRIPTS = WIN_INSTALL_SCRIPTS
        else:
            INSTALL_SCRIPTS = UNIX_INSTALL_SCRIPTS

        for filename in INSTALL_SCRIPTS:
            filepath = module.get_file(filename)
            if filepath:
                cmdline = []

                for arg in INSTALL_SCRIPTS[filename]:
                    cmdline.append(arg.format(filepath))

                results.append(cmdline)

        return results

    # Delete files older than 7 days and empty directories
    def clean_temp_dir(self, base):
        current_time = time()
        self.last_clean = current_time

        fame_path = os.path.dirname(os.path.abspath(__file__))
        if not fame_path in base:
            print(
                "WARNING: refusing to delete '{}' because it is outside of '{}'.".format(
                    base, fame_path
                )
            )
            return

        for root, dirs, files in os.walk(base, topdown=False):
            for f in files:
                filepath = os.path.join(root, f)
                file_mtime = os.path.getmtime(filepath)

                if (current_time - file_mtime) > (7 * 24 * 3600):
                    try:
                        os.remove(filepath)
                    except:
                        pass

            for d in dirs:
                dirpath = os.path.join(root, d)

                try:
                    os.rmdir(dirpath)
                except:
                    pass

    def run_cleaner(self):
        analyses, files = get_old_analyses()
        users = get_old_disabled_users()

        for analysis in analyses:
            print('Cleaner: Deleting analysis {}'.format(analysis['_id']))
            analysis.delete()

        for f in files:
            print('Cleaner: Deleting file {}'.format(f['_id']))
            f.delete()

        for user in users:
            print('Cleaner: Deleting user {}'.format(user['_id']))
            user.delete()

    def start(self):
        try:
            self.last_run = time()
            self.clean_temp_dir(fame_config.temp_path)
            self.update_modules()
            self.process = self._new_celery_worker()

            while True:
                updates = Internals.get(name='updates')
                if time() > (self.last_clean + 3600):
                    self.clean_temp_dir(fame_config.temp_path)
                    if fame_config.remote:
                        self.clean_temp_dir(fame_config.storage_path)

                    if 'updates' in self.queues:
                        self.run_cleaner()

                if updates['last_update'] > self.last_run:
                    # Stop running worker
                    os.kill(self.process.pid, signal.SIGTERM)
                    self.process.wait()

                    # Update modules if needed
                    self.update_modules()

                    # Restart worker
                    self.process = self._new_celery_worker()

                    self.last_run = time()

                sleep(self.refresh_interval)
        except KeyboardInterrupt:
            not_finished = True
            while not_finished:
                try:
                    self.process.wait()
                    not_finished = False
                except KeyboardInterrupt:
                    pass

    def _new_celery_worker(self):
        return Popen(['celery', '-A', 'fame.core.celeryctl', 'worker', '-Q', ','.join(self.queues)] + self.celery_args)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Launches a FAME worker.')
    parser.add_argument('queues', metavar='queue', type=str, nargs='*',
                        help='The task queues that this worker will handle.')
    parser.add_argument('-c', '--celery_args', type=str, default='',
                        help='Additional arguments for the celery worker.')
    parser.add_argument('-r', '--refresh_interval', type=int, default=30,
                        help='Frequency at which the worker will check for updates.')

    args = parser.parse_args()

    queues = args.queues

    # Default queue is 'unix'
    if len(queues) == 0:
        if sys.platform == 'win32':
            queues = ['windows']
        else:
            queues = ['unix']

    # A local worker should also take care of updates
    if not fame_config.remote:
        queues.append('updates')

    fame_init()
    Worker(queues, args.celery_args, args.refresh_interval).start()
