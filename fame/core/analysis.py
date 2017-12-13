import os
import requests
import datetime
import fcntl
import errno
import time
from shutil import copy
from hashlib import md5
from urlparse import urljoin

from fame.common.config import fame_config
from fame.common.utils import iterify, u, send_file_to_remote
from fame.common.mongo_dict import MongoDict
from fame.core.store import store
from fame.core.celeryctl import celery
from fame.core.module_dispatcher import dispatcher, DispatchingException


# Celery task to retrieve analysis object and run specific module on it
@celery.task
def run_module(analysis_id, module):
    dispatcher.reload()
    analysis = Analysis(store.analysis.find_one({'_id': analysis_id}))
    analysis.run(module)


class Analysis(MongoDict):
    STATUS_ERROR = 'error'
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_FINISHED = 'finished'

    collection_name = 'analysis'

    def __init__(self, values):
        self['status'] = self.STATUS_PENDING
        self['executed_modules'] = []
        self['pending_modules'] = []
        self['waiting_modules'] = []
        self['canceled_modules'] = []
        self['tags'] = []
        self['iocs'] = []
        self['results'] = {}
        self['generated_files'] = {}
        self['extracted_files'] = []
        self['support_files'] = {}
        self['logs'] = []
        self['extractions'] = []
        self['probable_names'] = []
        self['options'] = {}
        self['date'] = datetime.datetime.now()
        self['end_date'] = None
        self['groups'] = []
        self['analyst'] = []
        MongoDict.__init__(self, values)

        self._file = File(store.files.find_one({'_id': self['file']}))

        if '_id' not in self:
            self._init_threat_intelligence()
            self.save()

            if self['module'] is None:
                self._automatic()

    def add_generated_files(self, file_type, locations):
        # First, save the files to db / storage
        if file_type not in self['generated_files']:
            self['generated_files'][file_type] = []

        for location in iterify(locations):
            if fame_config.remote:
                response = send_file_to_remote(location, '/analyses/{}/generated_file'.format(self['_id']))
                filepath = response.json()['path']
            else:
                filepath = location

            self.log('debug', "Adding generated file '{0}' of type '{1}'".format(filepath, file_type))
            self.append_to(['generated_files', file_type], filepath)

        # Then, trigger registered modules
        self.queue_modules(dispatcher.triggered_by("_generated_file(%s)" % file_type))

    def add_extracted_file(self, filepath):
        self.log('debug', "Adding extracted file '{}'".format(filepath))

        fd = open(filepath, 'rb')
        filename = os.path.basename(filepath)
        f = File(filename=filename, stream=fd, create=False)

        if not f.existing:
            if fame_config.remote:
                response = send_file_to_remote(filepath, '/files/')
                f = File(response.json()['file'])
            else:
                f = File(filename=os.path.basename(filepath), stream=fd)

            f.analyze(self['groups'], self['analyst'], None, self['options'])

        fd.close()

        self.append_to('extracted_files', f['_id'])
        f.add_parent_analysis(self)

    def change_type(self, filepath, new_type):
        if self.get_main_file() == filepath:
            self._file.update_value('type', new_type)
            self._file.analyze(self['groups'], self['analyst'], None, self['options'])
        else:
            self.log('warning', "Tried to change type of generated file '{}'".format(filepath))

    def add_support_file(self, module_name, name, filepath):
        self.log('debug', "Adding support file '{}' at '{}'".format(name, filepath))

        if fame_config.remote:
            response = send_file_to_remote(filepath, '/analyses/{}/support_file/{}'.format(self['_id'], module_name))
            dstfilepath = response.json()['path']
        else:
            dirpath = os.path.join(fame_config.storage_path, 'support_files', module_name, str(self['_id']))
            dstfilepath = os.path.join(dirpath, os.path.basename(filepath))

            # Create parent dirs if they don't exist
            try:
                os.makedirs(dirpath)
            except:
                pass

            copy(filepath, dstfilepath)

        if module_name not in self['support_files']:
            self['support_files'][module_name] = []

        self.append_to(['support_files', module_name], (name, os.path.basename(dstfilepath)))

    def add_extraction(self, label, extraction):
        extraction_object = {'label': label, 'content': u(extraction)}
        self.append_to('extractions', extraction_object)

    def add_probable_name(self, probable_name):
        for name in self['probable_names']:
            if name.find(probable_name) != -1 or probable_name.find(name) != -1:
                break
        else:
            self._file.add_probable_name(probable_name)
            self.append_to('probable_names', probable_name)

    def add_ioc(self, value, source, tags=[]):
        # First, we need to make sure there is a record for this IOC
        r = self.collection.update_one({'_id': self['_id'], 'iocs.value': {'$ne': value}},
                                       {'$push': {'iocs': {'value': value, 'tags': [], 'ti_tags': [], 'ti_indicators': [], 'sources': []}}})

        # If this is the first time we are adding this IOC, lookup Threat Intelligence data
        if r.modified_count == 1:
            ti_tags, ti_indicators = self._lookup_ioc(value)
            # If we have Threat Intelligence data, enrich analysis
            if ti_tags:
                self.collection.update_one({'_id': self['_id'], 'iocs.value': value},
                                           {'$addToSet': {'iocs.$.ti_tags': {'$each': ti_tags}}})

            if ti_indicators:
                self.collection.update_one({'_id': self['_id'], 'iocs.value': value},
                                           {'$addToSet': {'iocs.$.ti_indicators': {'$each': ti_indicators}}})

        # Then add tags to the list
        self.collection.update_one({'_id': self['_id'], 'iocs.value': value},
                                   {'$addToSet': {'iocs.$.tags': {'$each': iterify(tags)}}})

        # Finally, add the source
        self.collection.update_one({'_id': self['_id'], 'iocs.value': value},
                                   {'$addToSet': {'iocs.$.sources': source}})

    # Starts / Resumes an analysis to reach the target module
    def resume(self):
        # First, see if there is pending modules remaining
        if self._run_pending_modules():
            return True
        else:
            # If not, look for a path to a waiting module
            for module in self['waiting_modules']:
                try:
                    next_module = dispatcher.next_module(self._types_available(), module, self._tried_modules())
                    self.queue_modules(next_module)
                    return True
                except DispatchingException:
                    self.remove_from('waiting_modules', module)
                    self.append_to('canceled_modules', module)

            # Finally, look for a path to the target
            if self['module'] is not None and self['module'] not in self['executed_modules']:
                try:
                    next_module = dispatcher.next_module(self._types_available(), self['module'], self._tried_modules())
                    self.queue_modules(next_module)
                    return True
                except DispatchingException:
                    self._error('Could not find execution path to target %s' % self['module'])

        return False

    # Queue execution of specific module(s)
    def queue_modules(self, modules, fallback_waiting=True):
        for module_name in iterify(modules):
            self.log("debug", "Trying to queue module '{0}'".format(module_name))
            if module_name not in self['executed_modules'] and module_name not in self['pending_modules']:
                module = self._get_module(module_name)

                if self._can_execute_module(module):
                    if self.append_to('pending_modules', module_name):
                        run_module.apply_async((self['_id'], module_name), queue=module.info['queue'])
                elif fallback_waiting:
                    self.append_to('waiting_modules', module_name)

    # Run specific module, should only be executed on celery worker
    def run(self, module_name):
        self.log('debug', "Trying to run {0}".format(module_name))
        print "Trying to run {0}".format(module_name)

        # This test prevents multiple execution of the same module
        if self.append_to('executed_modules', module_name):
            module = self._get_module(module_name)

            if module is None:
                self._error_with_module(module_name, "module has been removed or disabled.")
            else:
                try:
                    module.initialize()

                    self.update_value('status', self.STATUS_RUNNING)

                    if module.execute(self):
                        # Save results, if any
                        if module.results is not None:
                            self.update_value(['results', module_name], module.results)

                        # Save tags, and queue triggered modules
                        for tag in module.tags:
                            tag_string = "%s(%s)" % (module_name, tag)
                            self.add_tag(tag_string)

                        self.add_tag(module_name)

                    self.log('debug', "Done with {0}".format(module_name))
                except Exception, e:
                    self._error_with_module(module_name, str(e))

            self.remove_from('pending_modules', module_name)
            self.remove_from('waiting_modules', module_name)

        if not self.resume() and self['status'] != self.STATUS_ERROR:
            print "Finished !"
            self._mark_as_finished()

    def add_tag(self, tag):
        self.append_to('tags', tag)
        self.queue_modules(dispatcher.triggered_by(tag))

    def log(self, level, message):
        message = "%s: %s: %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), level, message)
        self.append_to('logs', message)

    # This will give the correct and locally valid filepath of given file
    # When on a remote worker, the file needs to be retrieved first
    def filepath(self, path):
        if fame_config.remote:
            pathhash = md5(path.encode('utf-8')).hexdigest()
            local_path = os.path.join(fame_config.storage_path, pathhash)
            lockname = os.path.expanduser('~') + '/' + pathhash
            lockfile = open(lockname, 'w+')
            locked = False
            while not locked:
                try:
                    fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                except:
                    time.sleep(1)

            if locked and not os.path.isfile(local_path):
                # Make sure fame_config.storage_path exists
                try:
                    os.makedirs(fame_config.storage_path)
                except:
                    pass

                url = urljoin(fame_config.remote, '/analyses/{}/get_file/{}'.format(self['_id'], pathhash))
                response = requests.get(url, stream=True, headers={'X-API-KEY': fame_config.api_key})
                response.raise_for_status()
                f = open(local_path, 'ab')
                for chunk in response.iter_content(1024):
                    f.write(chunk)
                f.close()

            try:
                os.remove(lockname)
            except:
                pass
            fcntl.flock(lockfile, fcntl.LOCK_UN)
            lockfile.close()

            return local_path
        else:
            return path

    def get_main_file(self):
        return self.filepath(self._file['filepath'])

    def get_files(self, file_type):
        results = []

        if file_type in self['generated_files']:
            for filepath in self['generated_files'][file_type]:
                results.append(self.filepath(filepath))

        if self._file['type'] == file_type:
            results.append(self.get_main_file())

        return results

    def _reporting_hook(self, hook_name):
        for module in dispatcher.get_reporting_modules():
            try:
                getattr(module, hook_name)(self)
            except Exception, e:
                self.log('error', "error in reporting module '{0}': {1}".format(module.name, e))

    def _lookup_ioc(self, ioc):
        ti_tags = []
        ti_indicators = []

        for module in dispatcher.get_threat_intelligence_modules():
            try:
                tags, indicators = module.ioc_lookup(ioc)
                ti_tags += tags
                ti_indicators += indicators
            except Exception, e:
                import traceback
                traceback.print_exc()
                self.log('error', "error in threat intelligence module '{}': {}".format(module.name, e))

        return ti_tags, ti_indicators

    def _init_threat_intelligence(self):
        self['threat_intelligence'] = {}

    def _mark_as_finished(self):
        self.update_value('status', self.STATUS_FINISHED)
        self.update_value('end_date', datetime.datetime.now())
        self._reporting_hook('done')

    def _get_module(self, module_name):
        return dispatcher.get_processing_module(module_name)

    def _error(self, reason):
        self.log('error', reason)
        self.update_value('status', self.STATUS_ERROR)
        self._reporting_hook('done')

    def _types_available(self):
        if self._file['type'] in self['generated_files']:
            return self['generated_files'].keys()
        else:
            return self['generated_files'].keys() + [self._file['type']]

    # Determine if a module could be run on the current status of analysis
    def _can_execute_module(self, module):
        if not module.info['acts_on']:
            return True
        else:
            for source_type in iterify(module.info['acts_on']):
                if source_type in self._types_available():
                    return True

            return False

    # Returns True if any module was in the queue
    def _run_pending_modules(self):
        self.refresh()

        if len(self['pending_modules']) == 0:
            return False
        else:
            return True

    def _tried_modules(self):
        return self['executed_modules'] + self['canceled_modules']

    # Automatic analysis
    def _automatic(self):
        if len(self['pending_modules']) == 0 and self['status'] == 'pending':
            self.queue_modules(dispatcher.general_purpose(), False)

        if len(self['pending_modules']) == 0:
            self._mark_as_finished()

    def _error_with_module(self, module, message):
        self.log("error", "{}: {}".format(module, message))
        self.append_to('canceled_modules', module)


# For cyclic imports
from fame.core.file import File
