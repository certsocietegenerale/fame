import os
import requests
import traceback

from bson import json_util
from hashlib import md5
from urlparse import urljoin

from fame.common.config import fame_config
from fame.core.analysis import Analysis as CoreAnalysis
from fame.core.celeryctl import celery
from fame.core.file import File
from fame.core.module_dispatcher import dispatcher
from fame.core.store import store
from fame.worker.utils import send_file_to_remote


# Celery task to retrieve analysis object and run specific module on it
@celery.task(name="run_module")
def run_module(analysis_id, module):
    dispatcher.reload()
    analysis = Analysis(store.analysis.find_one({'_id': analysis_id}))
    analysis.run(module)


class Analysis(CoreAnalysis):
    def __init__(self, values):
        super(Analysis, self).__init__(values)

    def _get_generated_file_path(self, location):
        response = send_file_to_remote(
            location, '/analyses/{}/generated_file'.format(self['_id']))
        return response.json()['path']

    def _get_file_from_filepath(self, filepath, fd=None):
        response = send_file_to_remote(filepath, '/files/')
        return File(json_util.loads(response.text)['file'])

    def _store_preloaded_file(self, filepath=None, fd=None):
        if not filepath and not fd:
            raise ValueError(
                "Please provide either the path to the file or a file-like "
                "object containing the data.")

        if filepath and fd:
            self.log("debug",
                     "Please provide either the path to the file or a "
                     "file-like object containing the data, not both. "
                     "Chosing the file-like object for now.")
            response = send_file_to_remote(fd, '/files/')
        else:
            response = send_file_to_remote(filepath, '/files/')

        return File(json_util.loads(response.text)['file'])

    def _store_support_file(self, filepath, module_name):
        response = send_file_to_remote(
            filepath, '/analyses/{}/support_file/{}'.format(
                self['_id'], module_name))
        return response.json()['path']

    # Run specific module, should only be executed on celery worker
    def run(self, module_name):
        self.log('debug', "Trying to run {0}".format(module_name))
        print "Trying to run {0}".format(module_name)

        # This test prevents multiple execution of the same module
        if self.append_to('executed_modules', module_name):
            module = dispatcher.get_module(module_name)

            if module is None:
                self._error_with_module(
                    module_name, "module has been removed or disabled.")
            else:
                try:
                    module.initialize()

                    if module.info['type'] == "Preloading":
                        self.update_value('status', self.STATUS_PRELOADING)
                    else:
                        self.update_value('status', self.STATUS_RUNNING)

                    if module.execute(self):
                        # Save results, if any
                        if module.results is not None:
                            self.update_value(['results', module_name],
                                              module.results)

                        # Save tags, and queue triggered modules
                        for tag in module.tags:
                            tag_string = "%s(%s)" % (module_name, tag)
                            self.add_tag(tag_string)

                        self.add_tag(module_name)

                    elif module.info['type'] == "Preloading":
                        # queue next preloading module
                        next_module = dispatcher.get_next_preloading_module(
                            self._types_available(), self._tried_modules())
                        if next_module:
                            self.queue_modules(next_module)

                    self.log('debug', "Done with {0}".format(module_name))
                except Exception:
                    tb = traceback.format_exc()
                    self._error_with_module(module_name, tb)

            self.remove_from('pending_modules', module_name)
            self.remove_from('waiting_modules', module_name)

        self.resume()

    # This will give the correct and locally valid filepath of given file
    # When on a remote worker, the file needs to be retrieved first
    # Thus we overload the function in this subclass to have that transparent
    def filepath(self, path):
        pathhash = md5(path.encode('utf-8')).hexdigest()
        # Some modules require proper filenames, so don't join with just pathhash
        local_path = os.path.join(fame_config.storage_path, pathhash, os.path.basename(path))
        if not os.path.isfile(local_path):
            # Make sure local_path exists
            try:
                os.makedirs(os.path.dirname(local_path))
            except OSError:
                pass

            url = urljoin(
                fame_config.remote, '/analyses/{}/get_file/{}'.format(
                    self['_id'], pathhash))

            response = requests.get(url, stream=True,
                                    headers={'X-API-KEY': fame_config.api_key})
            response.raise_for_status()

            f = open(local_path, 'wb')
            for chunk in response.iter_content(1024):
                f.write(chunk)

            f.close()

        return local_path

    def get_main_file(self):
        filepath = self._file['filepath']
        if self._file['type'] == "hash":
            return filepath
        return self.filepath(filepath)
