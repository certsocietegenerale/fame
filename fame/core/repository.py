import os
from time import time
from shutil import rmtree
from git import Repo

from fame.common.mongo_dict import MongoDict
from fame.common.constants import FAME_ROOT
from fame.core.celeryctl import celery
from fame.core.module import ModuleInfo
from fame.core.internals import Internals
from fame.core.module_dispatcher import dispatcher


# Celery task to retrieve analysis object and run specific module on it
@celery.task(soft_time_limit=60)
def clone_repository(repository_id):
    repository = Repository.get(_id=repository_id)
    repository.do_clone()


@celery.task(soft_time_limit=60)
def pull_repository(repository_id):
    repository = Repository.get(_id=repository_id)
    repository.do_pull()


class Repository(MongoDict):
    collection_name = 'repositories'

    def __init__(self, values={}):
        keyfile = os.path.join(FAME_ROOT, "conf", "id_rsa")
        self['ssh_cmd'] = "ssh -o StrictHostKeyChecking=no -i {}".format(keyfile)
        MongoDict.__init__(self, values)

    def delete(self):
        # First, remove modules from database
        for module in ModuleInfo.find():
            if module['path'].startswith('fame.modules.{}.'.format(self['name'])):
                module.delete()

        # Then, delete the files
        try:
            rmtree(self.path())
        except:
            pass

        # Finally, delete record of repository
        MongoDict.delete(self)

    def path(self):
        return os.path.join(FAME_ROOT, 'fame', 'modules', self['name'])

    def clone(self):
        clone_repository.apply_async((self['_id'],), queue='updates')

    def do_clone(self):
        print(("[+] Cloning '{}'".format(self['name'])))
        try:
            if self['private']:
                Repo.clone_from(self['address'], self.path(), env=dict(GIT_SSH_COMMAND=self['ssh_cmd']))
            else:
                Repo.clone_from(self['address'], self.path())

            dispatcher.update_modules(self)
            if self['status'] == 'cloning':
                self.update_value('status', 'active')
        except Exception as e:
            self['status'] = 'error'
            self['error_msg'] = 'Could not clone repository, probably due to authentication issues.\n{}'.format(e)
            self.save()

        internals = Internals.get(name="updates")
        internals.update_value("last_update", time())

    def pull(self):
        self.update_value('status', 'updating')
        pull_repository.apply_async((self['_id'],), queue='updates')

    def do_pull(self):
        print(("[+] Pulling '{}'".format(self['name'])))
        try:
            repo = Repo(self.path())

            if self['private']:
                with repo.git.custom_environment(GIT_SSH_COMMAND=self['ssh_cmd']):
                    repo.remotes.origin.pull()
            else:
                repo.remotes.origin.pull()

            # Make sure we delete orphan .pyc files
            for root, dirs, files in os.walk(self.path()):
                for f in files:
                    f = os.path.join(root, f)
                    if f.endswith(".pyc") and not os.path.exists(f[:-1]):
                        print(("Deleting orphan file '{}'".format(f)))
                        os.remove(f)

            dispatcher.update_modules(self)
            if self['status'] == 'updating':
                self.update_value('status', 'active')
        except Exception as e:
            self['status'] = 'error'
            self['error_msg'] = 'Could not update repository.\n{}'.format(e)
            self.save()

        updates = Internals.get(name="updates")
        updates.update_value("last_update", time())
