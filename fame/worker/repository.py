import os
import requests

from time import time
from git import Repo
from tempfile import mkdtemp, TemporaryFile
from urlparse import urljoin
from zipfile import ZipFile
from io import BytesIO

from fame.common.config import fame_config
from fame.common.constants import FAME_ROOT
from fame.core.celeryctl import celery
from fame.core.internals import Internals
from fame.core.repository import Repository as CoreRepository


@celery.task(soft_time_limit=60, name="refresh_repository")
def refresh_repository(repository_id):
    repository = Repository.get(_id=repository_id)

    # load current module blob from remote
    url = urljoin(fame_config.fame_url, '/modules/download')
    try:
        print "[+] Get current modules"
        response = requests.get(
            url, stream=True, headers={'X-API-KEY': fame_config.api_key})
        response.raise_for_status()

        print "[+] Extract modules"
        module_tempdir = mkdtemp()
        with ZipFile(BytesIO(response.content), 'r') as zipf:
            zipf.extractall(module_tempdir)

        print "[+] Constructing git repository path"
        repo_path = os.path.join(module_tempdir, repository['name'])

        success = False

        if os.path.exists(repo_path):
            # path exists
            if os.path.isdir(repo_path):
                if len(os.listdir(repo_path)) == 0:
                    # directory empty
                    print "[+] Cloning into existing directory"
                    repository['status'] = 'cloning'
                    repository.save()
                    success = repository.do_clone(path=repo_path)

                else:
                    git_folder = os.path.join(repo_path, ".git")

                    # path contains .git folder -> pull
                    if os.path.exists(git_folder) and os.path.isdir(git_folder):  # noqa
                        print "[+] Pulling latest changes"
                        repository['status'] = 'pulling'
                        repository.save()
                        success = repository.do_pull(path=repo_path)
                    else:
                        raise "Took unexpected path in program logic!"

            else:
                raise "Path exists but is not a directory"
        else:
            # directory empty
            print "[+] Cloning new repository"
            repository['status'] = 'cloning'
            repository.save()
            success = repository.do_clone(path=repo_path)

        if not success:
            # Error was set by do_pull/do_clone
            print "[E] Could not update repository"
            return

        print "[+] Zipping files up"
        with TemporaryFile() as tempf:
            with ZipFile(tempf, 'w') as zipf:
                for root, dirs, files in os.walk(repo_path):
                    for filename in files:
                        # Ignore pyc files
                        if not filename.endswith('.pyc'):
                            filepath = os.path.join(root, filename)
                            zipf.write(
                                filepath, os.path.relpath(filepath, repo_path))

            print "[+] Putting files to web server"
            url = urljoin(
                fame_config.fame_url,
                '/modules/repository/{}/update'.format(repository['_id']))
            tempf.seek(0)
            resp = requests.put(
                url,
                data=tempf,
                headers={
                    'X-API-KEY': fame_config.api_key,
                    'Content-Type': 'application/zip'
                })
            resp.raise_for_status()

    except Exception as e:
        repository['status'] = 'error'
        repository['error_msg'] = e.message
        repository.save()
        print "[E] Could not update repository: {}".format(e.message)
    else:
        print "[*] Job success"


class Repository(CoreRepository):
    def __init__(self, values={}):
        keyfile = os.path.join(FAME_ROOT, "conf", "id_rsa")
        self['ssh_cmd'] = "ssh -o StrictHostKeyChecking=no -i {}".format(keyfile)

        super(Repository, self).__init__(values)

    def do_clone(self, path=None):
        print "[+] Cloning '{}'".format(self['name'])
        try:
            if self['private']:
                Repo.clone_from(self['address'], path or self.path(),
                                env=dict(GIT_SSH_COMMAND=self['ssh_cmd']))
            else:
                Repo.clone_from(self['address'], path or self.path())

            internals = Internals.get(name="updates")
            internals.update_value("last_update", time())
            return True

        except Exception, e:
            self['status'] = 'error'
            self['error_msg'] = 'Could not clone repository, probably due to authentication issues.\n{}'.format(e)  # noqa
            self.save()
            return False

    def do_pull(self, path=None):
        print "[+] Pulling '{}'".format(self['name'])
        try:
            repo = Repo(path or self.path())

            if self['private']:
                with repo.git.custom_environment(
                        GIT_SSH_COMMAND=self['ssh_cmd']):
                    repo.remotes.origin.pull()
            else:
                repo.remotes.origin.pull()

            # Make sure we delete orphan .pyc files
            for root, dirs, files in os.walk(path or self.path()):
                for f in files:
                    f = os.path.join(root, f)
                    if f.endswith(".pyc") and not os.path.exists(f[:-1]):
                        print "Deleting orphan file '{}'".format(f)
                        os.remove(f)

            updates = Internals.get(name="updates")
            updates.update_value("last_update", time())
            return True
        except Exception, e:
            self['status'] = 'error'
            self['error_msg'] = 'Could not update repository.\n{}'.format(e)
            self.save()
            return False
