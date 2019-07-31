from __future__ import print_function
import os
import sys
import signal
import argparse
import requests
from urlparse import urljoin
from socket import gethostname
from StringIO import StringIO
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


UNIX_INSTALL_SCRIPTS = {
    "install.sh": ["bash", "{}"],
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
            move(MODULES_ROOT, backup_path)

            # Replace current code with code fetched from web server
            url = urljoin(fame_config.remote, '/modules/download')
            try:
                response = requests.get(url, stream=True, headers={'X-API-KEY': fame_config.api_key})
                response.raise_for_status()

                os.makedirs(MODULES_ROOT)
                with ZipFile(StringIO(response.content), 'r') as zipf:
                    zipf.extractall(MODULES_ROOT)

                rmtree(backup_path)
                print("Updated modules.")
            except Exception, e:
                print("Could not update modules: '{}'".format(e))
                print("Restoring previous version")
                move(backup_path, MODULES_ROOT)

        self.update_module_requirements()

    def update_module_requirements(self):
        for module in ModuleInfo.get_collection().find():
            module = ModuleInfo(module)

            if 'error' in module:
                del(module['error'])

            if module['type'] == "Processing":
                should_update = (module['queue'] in self.queues)
            elif module['type'] in ["Preloading", "Threat Intelligence", "Reporting", "Filetype"]:
                should_update = True
            else:
                should_update = (not fame_config.remote)

            if should_update and module['enabled']:
                self.update_python_requirements(module)
                self.launch_install_scripts(module)

            module.save()

    def update_python_requirements(self, module):
        requirements = self._module_requirements(module)

        if requirements:
            print("Installing requirements for '{}' ({})".format(module['name'], requirements))

            rcode, output = pip_install('-r', requirements)

            # In case pip failed
            if rcode:
                self._module_installation_error(requirements, module, output)

    def launch_install_scripts(self, module):
        scripts = self._module_install_scripts(module)

        for script in scripts:
            try:
                print("Launching installation script '{}'".format(' '.join(script)))
                check_output(script, stderr=STDOUT)
            except CalledProcessError, e:
                self._module_installation_error(' '.join(script), module, e.output)
            except Exception, e:
                self._module_installation_error(' '.join(script), module, e)

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
    def clean_temp_dir(self):
        current_time = time()

        for root, dirs, files in os.walk(fame_config.temp_path, topdown=False):
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

    def start(self):
        try:
            self.last_run = time()
            self.clean_temp_dir()
            self.update_modules()
            self.process = self._new_celery_worker()

            while True:
                updates = Internals.get(name='updates')
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
        return Popen(['celery', '-A', 'fame.core.celeryctl', 'worker', '-Q', ','.join(self.queues)] + self.celery_args,
                     stdout=sys.stdout, stderr=sys.stderr)

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

    # ensure workers also listen to update requests if *nix
    if "unix" in queues:
        queues.append("updates")

    fame_init()
    Worker(queues, args.celery_args, args.refresh_interval).start()
