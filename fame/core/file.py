from bson import ObjectId
import hashlib
import os
import magic
import datetime

from fame.core.store import store
from fame.common.config import ConfigObject, fame_config
from fame.common.mongo_dict import MongoDict
from fame.core.module_dispatcher import dispatcher
from fame.core.config import Config


class File(MongoDict):
    collection_name = 'files'

    def __init__(self, values=None, filename=None, stream=None, create=True):
        # When only passing a dict
        if isinstance(values, dict):
            MongoDict.__init__(self, values)
            self['comments'] = []
        else:
            MongoDict.__init__(self, {})
            self['probable_names'] = []
            self['parent_analyses'] = []
            self['groups'] = []
            self['owners'] = []
            self['comments'] = []

            # filename should be set
            if filename is not None and stream is not None:
                self._compute_hashes(stream)

            # If the file already exists in the database, update it
            self.existing = False
            existing_file = self.collection.find_one({'sha256': self['sha256']})
            if existing_file:
                self._add_to_previous(existing_file, filename)
                self.existing = True
            # Otherwise, compute default properties and save
            elif create:
                self._store_file(filename, stream)
                self._compute_default_properties()
                self.save()

    def add_comment(self, analyst_id, comment, analysis_id=None, probable_name=None):
        if probable_name:
            self.add_probable_name(probable_name)

        self.append_to('comments', {
            'analyst': analyst_id,
            'comment': comment,
            'analysis': analysis_id,
            'probable_name': probable_name,
            'date': datetime.datetime.now()
        })

    def add_probable_name(self, probable_name):
        for name in self['probable_names']:
            if name.find(probable_name) != -1 or probable_name.find(name) != -1:
                break
        else:
            self.append_to('probable_names', probable_name)

    def add_owners(self, owners):
        for owner in owners:
            self.append_to('owners', owner)

    def remove_group(self, group):
        # Update file
        self.remove_from('groups', group)

        # Update previous analysis
        for analysis_id in self['analysis']:
            analysis = Analysis(store.analysis.find_one({'_id': ObjectId(analysis_id)}))
            analysis.remove_from('groups', group)

    def add_groups(self, groups):
        # Update file
        for group in groups:
            self.append_to('groups', group)

        # Update previous analysis
        for analysis_id in self['analysis']:
            analysis = Analysis(store.analysis.find_one({'_id': ObjectId(analysis_id)}))
            for group in groups:
                analysis.append_to('groups', group)

    # Tries to perform 'module_name' on this file
    def analyze(self, groups, analyst, modules=None, options=None):
        analysis = Analysis({
            'file': self['_id'],
            'modules': modules or [],
            'options': options or {},
            'groups': list(set(groups + self['groups'])),
            'analyst': analyst
        })
        analysis.save()

        self.add_groups(groups)
        self.append_to('analysis', analysis['_id'])

        analysis.resume()

        return analysis

    def add_parent_analysis(self, analysis):
        self.append_to('parent_analyses', analysis['_id'])

    # Update existing record
    def _add_to_previous(self, existing_record, name):
        self.update(existing_record)
        self.append_to('names', name)

    # Compute Hashes for current file
    def _compute_hashes(self, stream):
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        sha256 = hashlib.sha256()

        while True:
            data = stream.read(4096)
            if data:
                md5.update(data)
                sha1.update(data)
                sha256.update(data)
            else:
                stream.seek(0, 0)
                break

        self['md5'] = md5.hexdigest()
        self['sha1'] = sha1.hexdigest()
        self['sha256'] = sha256.hexdigest()

    # Compute default properties
    # For now, just 'name' and 'type'
    def _compute_default_properties(self):
        self['names'] = [os.path.basename(self['filepath'])]
        self['detailed_type'] = magic.from_file(self['filepath'])
        self['mime'] = magic.from_file(self['filepath'], mime=True)
        self['size'] = os.path.getsize(self['filepath'])
        self['analysis'] = []

        # Init antivirus status
        self['antivirus'] = {}

        for module in dispatcher.get_antivirus_modules():
            self['antivirus'][module.name] = False

        self._set_type()

    # Convert mime/types into clearer type
    def _set_type(self):
        config = Config.get(name="types").get_values()
        config = ConfigObject(from_string=config.mappings)
        detailed_types = config.get('details')
        extensions = config.get('extensions')

        self['type'] = self['mime']

        # First, look at extensions
        for ext in extensions:
            if self['filepath'].split('.')[-1].lower() == ext:
                self['type'] = extensions.get(ext)
                break
        # Otherwise, look in 'detailed_types'
        else:
            for t in detailed_types:
                if self['detailed_type'].lower().startswith(t.lower()):
                    self['type'] = detailed_types.get(t)
                    break
            # Or mime types
            else:
                types = config.get("types")
                if types.get(self['mime']) is not None:
                    self['type'] = types.get(self['mime'])

        # Run Filetype modules, starting with the most specific ones
        filetype_modules = dispatcher.get_filetype_modules_for(self['type'])
        filetype_modules += dispatcher.get_filetype_modules_for('*')

        for module in filetype_modules:
            try:
                known_type = module.recognize(self['filepath'], self['type'])
                if known_type:
                    self['type'] = known_type
                    break
            except:
                pass

    def _store_file(self, filename, stream):
        self['filepath'] = u'{0}/{1}'.format(self['sha256'], filename)
        self['filepath'] = os.path.join(fame_config.storage_path, self['filepath'])

        # Create parent dirs if they don't exist
        try:
            os.makedirs(os.path.join(fame_config.storage_path, self['sha256']))
        except:
            pass

        # Save file contents
        with open(self['filepath'], "wb") as fd:
            while True:
                data = stream.read(4096)
                if data:
                    fd.write(data)
                else:
                    stream.seek(0, 0)
                    break

# For cyclic imports
from fame.core.analysis import Analysis
