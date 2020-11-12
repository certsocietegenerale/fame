import os

from shutil import rmtree

from fame.common.mongo_dict import MongoDict
from fame.common.constants import FAME_ROOT
from fame.core.celeryctl import celery
from fame.core.module import ModuleInfo


class Repository(MongoDict):
    collection_name = 'repositories'

    def delete(self):
        # First, remove modules from database
        for module in ModuleInfo.find():
            if module['path'].startswith('fame.modules.{}.'.format(self['name'])):  # noqa
                module.delete()

        # Then, delete the files
        try:
            rmtree(self.path())
        except OSError:
            pass

        # Finally, delete record of repository
        MongoDict.delete(self)

    def path(self):
        return os.path.join(FAME_ROOT, 'fame', 'modules', self['name'])

    def update_files(self):
        celery.send_task('refresh_repository',
                         args=(self['_id'],),
                         queue='updates')
