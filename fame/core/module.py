import os
import traceback

from fame.common.constants import MODULES_ROOT
from fame.common.exceptions import ModuleInitializationError, ModuleExecutionError, MissingConfiguration
from fame.common.utils import iterify, is_iterable, list_value
from fame.common.mongo_dict import MongoDict
from fame.core.config import Config, apply_config_update, incomplete_config


def init_config_values(info):
    for config in info['config']:
        config['value'] = None

        if config['type'] == 'bool' and config['default']:
            config['value'] = config['default']


class ModuleInfo(MongoDict):
    collection_name = 'modules'

    def get_file(self, filename):
        path = os.path.join(MODULES_ROOT, *(self['path'].split('.')[2:]))

        if os.path.isdir(path):
            filepath = os.path.join(path, filename)
        else:
            filepath = os.path.join(os.path.dirname(path), filename)

        if os.path.isfile(filepath):
            return filepath

        return None

    def details_template(self):
        return '/'.join(self['path'].split('.')[2:-1]) + '/details.html'

    def update_config(self, new_info):
        if self['type'] == 'Processing':
            self['generates'] = new_info['generates']

            self['queue'] = new_info['queue']
            if 'queue' in self['diffs']:
                if self['diffs']['queue'] == new_info['queue']:
                    del self['diffs']['queue']
                else:
                    self['queue'] = self['diffs']['queue']

            self._update_diffed_value('acts_on', new_info['acts_on'])
            self._update_diffed_value('triggered_by', new_info['triggered_by'])

        self['description'] = new_info['description']
        self['config'] = apply_config_update(self['config'], new_info['config'])

        if self['enabled'] and incomplete_config(self['config']):
            self['enabled'] = False

        self.save()

    def update_setting_value(self, name, value):
        if is_iterable(self[name]):
            value = list_value(value)

            for element in value:
                if element not in self[name]:
                    self._add_value(name, element)

            for element in self[name]:
                if element not in value:
                    self._remove_value(name, element)

            self[name] = value
        else:
            if self[name] != value:
                self['diffs'][name] = value
                self[name] = value

    def _init_list_diff(self, name):
        if 'diffs' not in self:
            self['diffs'] = {}

        if name not in self['diffs']:
            self['diffs'][name] = {
                'added': [],
                'removed': []
            }

    def _add_value(self, name, value):
        self._init_list_diff(name)

        if value in self['diffs'][name]['removed']:
            self['diffs'][name]['removed'].remove(value)
        else:
            self['diffs'][name]['added'].append(value)

    def _remove_value(self, name, value):
        self._init_list_diff(name)

        if value in self['diffs'][name]['added']:
            self['diffs'][name]['added'].remove(value)
        else:
            self['diffs'][name]['removed'].append(value)

    def _update_diffed_value(self, name, value):
        self._init_list_diff(name)
        self[name] = value

        if name in self['diffs']:
            new_removed = []
            for element in self['diffs'][name]['removed']:
                if element in self[name]:
                    self[name].remove(element)
                    new_removed.append(element)

            self['diffs'][name]['removed'] = new_removed

            new_added = []
            for element in self['diffs'][name]['added']:
                if element not in self[name]:
                    self[name].append(element)
                    new_added.append(element)

            self['diffs'][name]['added'] = new_added


class Module(object):
    """Base class for every kind of modules used by FAME.

    Define functions that can be used by every kind of modules.

    Attributes:
        name: A string that defines the name of the module. This is what will be
            displayed in the interface. A module without a ``name`` is an
            abstract module.

        description: A string describing what this module does. It will be
            displayed to the user in the interface.

        config: Module configuration options. This attribute should be a list
            of dicts with the following form::

                {
                    'name': 'NAME',
                    'type': 'TYPE', # 'str', 'integer', 'bool' or 'text'
                    'default': 'DEFAULT',
                    'description': 'The description.'
                },

            The following fields are available:

            * ``name``: name of this setting. Will determine how to access this setting in the module.
            * ``description``: a description of this setting, to help the user / administrator.
            * ``type``: can be ``str``, ``integer``, ``bool`` or ``text``. The difference between ``text`` and ``str`` is only the representation of the setting in forms (input for ``str``, textarea for ``text``).
            * ``default`` (optional): default value.
            * ``option`` (optional): should this setting be available on a per-analysis basis ? Default value is ``False``.

        named_configs: Configuration shared between modules. Typically used in
            abstract modules. This is a dict, with each key being the name of
            a configuration group, and the value being a dict with two fields:

            * ``description``: a description of this configuration group.
            * ``config``: a list of dicts, similar to :attr:`fame.core.module.Module.config`.

            Example::

                named_configs = {
                    'configuration_group': {
                        'description': 'This is a shared configuration',
                        'config': [
                            {
                                'name': 'NAME',
                                'type': 'TYPE',
                                'description': 'Description of this setting'
                            }
                        ]
                    }
                }
    """
    name = None
    config = []
    named_configs = {}
    description = None

    def __init__(self, with_config=True):
        self._analysis = None

        if with_config:
            self.init_config()

    def needs_variable(self, variables):
        """Indicate that the module needs a specific attribute to work properly.

        This function is only useful in abstract modules, in order to make sure
        that modules that inherit from this class correctly defines needed class
        attributes.

        Args:
            variables: a string or an array of strings containing the name of
                needed class attributes.

        Raises:
            ModuleInitializationError: One of the needed attributes is not
                correctly defined.
        """
        for variable in iterify(variables):
            if getattr(self, variable) is None:
                raise ModuleInitializationError(self, "no '%s' defined" % variable)

    def initialize(self):
        """To implement in module to perform initialization operations.

        All dependency verifications should be done by defining this method
        in modules.

        Raises:
            ModuleInitializationError: Should be raised for any initialization
                error, with a message.
        """
        return True

    def init_config(self):
        for named_config in self.named_configs:
            config = Config.get(name=named_config)
            if config is None:
                raise MissingConfiguration("Missing '{}' configuration".format(named_config))

            setattr(self, named_config, config.get_values())

        for config in self.info['config']:
            if (config['value'] is None) and ('default' not in config):
                raise MissingConfiguration("Missing configuration value: {}".format(config['name']))

            setattr(self, config['name'], config['value'] or config['default'])

    @classmethod
    def named_config(cls, name):
        config = {
            'name': name,
            'description': cls.named_configs[name]['description'],
            'config': cls.named_configs[name]['config']
        }

        init_config_values(config)

        return config


class ProcessingModule(Module):
    """Base class for processing modules

    This class provides several methods that can update the analysis with
    interesting findings.

    Attributes:
        acts_on: A string or a list of strings containing FAME files type that
            can be analyzed by this module. Default value of ``None`` means all
            file types.

        generates: A string or a list of strings containing FAME files type that
            can be generated by this module. This will be used for module
            chaining in the case of :ref:`concept-targeted`. Default value of
            ``None`` means no files are generated.

        triggered_by: A string or a list of strings containing fnmatch patterns
            that will match analysis tags in order to determine if this module
            should run. Default value of ``None`` creates a generic module, that
            will always execute on the types of files it acts on.

        queue: A string defining on which queue the tasks will be added. This
            defines on which worker this module will execute. The default
            value is `unix`.

        permissions: A dictionnary listing permissions used by this module.
            Each key is the name of a permission, and the value is a
            description::

                permissions = {
                    'permission_name': "Description of the permission."
                }

            The default value is ``{}``, which means the module does not
            use any permission.
    """
    acts_on = []
    generates = []
    triggered_by = []
    permissions = {}
    queue = 'unix'

    def __init__(self, with_config=True):
        Module.__init__(self, with_config)
        self.results = None
        self.tags = []

    def log(self, level, message):
        """Add a log message to the analysis

        Args:
            level: string to define the log level (``debug``, ``info``, ``warning`` or ``error``).
            message: free text message containing the log information.
        """
        self._analysis.log(level, "%s: %s" % (self.name, message))

    def register_files(self, file_type, locations):
        """Add a generated file to the analysis.

        Args:
            file_type (string): FAME file type of the generated file.
            location (string): full path of the file, or array of full path."""
        self._analysis.add_generated_files(file_type, locations)

    def change_type(self, location, new_type):
        """Change the type of a file and launch a new analysis.

        Args:
            location (string): path of the file to change.
            new_type (string): new FAME file type."""
        self._analysis.change_type(location, new_type)

    def add_extracted_file(self, location):
        """Create a new file that deserves its own analysis.

        Args:
            location (string): full path."""
        self._analysis.add_extracted_file(location)

    def add_support_file(self, name, location):
        """Add a support file to this analysis. A support file is a file that
        will be stored permanently and you will be able for analysts to download.

        Args:
            name (string): name of this support file.
            location (string): full path. The name of the file will be kept.
                You should ensure that you use filenames that cannot generate
                collisions. For example, you could use the module name as a
                prefix."""
        self._analysis.add_support_file(self.name, name, location)

    def add_extraction(self, label, extraction):
        """Add an extraction to the analysis.

        Args:
            label (string): name of this extraction.
            extraction (string): extraction content.
        """
        self._analysis.add_extraction(label, extraction)

    def add_probable_name(self, probable_name):
        """Add a probable name to the analysis.

        Args:
            probable_name (string): probable name of the malware.
        """
        self._analysis.add_probable_name(probable_name)

    def add_ioc(self, value, tags=[]):
        """Add IOCs to the analysis.

        Args:
            value: string or list of strings containing the IOC's value.
            tags (optional): string or list of strings containing tags that
                describe these IOCs.
        """
        for ioc in iterify(value):
            self._analysis.add_ioc(ioc, self.name, tags)

    def add_tag(self, tag):
        """Add a tag to the analysis.

        All tags added using this method will only be added to the analysis if
        the module's execution returns ``True``.

        Args:
            tag (string): tag to add to the analysis. Tags added to the analysis
                will have the following format: ``module_name[tag]``.
        """
        if tag not in self.tags:
            self.tags.append(tag)

    def init_options(self, options):
        for option in options:
            setattr(self, option, options[option])

    def execute(self, analysis):
        self._analysis = analysis
        self.init_options(analysis['options'])
        return self.run()

    def each(self, target):
        """To implement. Perform the actual analysis.

        This method will automatically be called once for every file in the
        analysis matching the :attr:`acts_on` attribute.

        Should return ``True`` if the module succeeded, and add any useful
        information to ``self.results`` (format of this instance variable is
        free as long as it can be encoded with BSON).

        Args:
            target (string): full path of the file to analyze. URL string when
                the object to analyze is a URL.

        Returns:
            boolean indicating if module was successful.

        Raises:
            ModuleExecutionError: if any error occurs during the analysis.
        """
        self.log("warning", "no 'each' method defined. Module should define 'each' or 'run'")
        return False

    def each_with_type(self, target, file_type):
        """To implement. Perform the actual analysis.

        This method is similar to :func:`each`, but has an additional argument,
        which is the type of the target. When creating a module, you can chose
        between implementing :func:`each` or :func:`each_with_type`.

        Args:
            target (string): full path of the file to analyze. URL string when
                the object to analyze is a URL.
            file_type (string): FAME type of the target.

        Returns:
            boolean indicating if module was successful.

        Raises:
            ModuleExecutionError: if any error occurs during the analysis.
        """
        return self.each(target)

    def run(self):
        """To implement, when :func:`fame.core.module.ProcessingModule.each` cannot be used.

        This method will be called and should perform the actual analysis. It
        should have the same output than :func:`fame.core.module.ProcessingModule.each`.

        By default, it will call :func:`fame.core.module.ProcessingModule.each`
        on every elligible file in the analysis.

        You should only define this method when the module does not work on
        files, but on the analysis itself. The analysis can be accessed using
        ``self._analysis``.

        Returns:
            boolean indicating if module was successful.

        Raises:
            ModuleExecutionError: if any error occurs during the analysis.
        """
        result = False

        # Process all the files available for this module,
        # if 'acts_on' is defined
        if self.info['acts_on']:
            for source_type in iterify(self.info['acts_on']):
                for target in self._analysis.get_files(source_type):
                    if self._try_each(target, source_type):
                        result = True
        # Otherwise, only run on main target
        else:
            return self._try_each(self._analysis.get_main_file(), self._analysis._file['type'])

        return result

    def _try_each(self, target, file_type):
        try:
            if file_type == 'url':
                with open(target, 'rb') as fd:
                    target = fd.read()
            return self.each_with_type(target, file_type)
        except ModuleExecutionError, e:
            self.log("error", "Could not run on %s: %s" % (target, e))
            return False
        except:
            tb = traceback.format_exc()
            self.log("error", "Could not run on %s.\n %s" % (target, tb))
            return False

    @classmethod
    def static_info(cls):
        info = {
            "name": cls.name,
            "description": cls.description,
            "type": "Processing",
            "config": cls.config,
            "diffs": {},
            "acts_on": iterify(cls.acts_on),
            "generates": iterify(cls.generates),
            "triggered_by": iterify(cls.triggered_by),
            "queue": cls.queue
        }

        init_config_values(info)

        return ModuleInfo(info)


class ReportingModule(Module):
    """Base class for reporting modules"""

    def initialize(self):
        return True

    def done(self, analysis):
        """To implement. Called when an analysis is finished.

        Args:
            analysis: the finished analysis.
        """
        pass

    @classmethod
    def static_info(cls):
        info = {
            "name": cls.name,
            "description": cls.description,
            "type": "Reporting",
            "config": cls.config,
            "diffs": {},
        }

        init_config_values(info)

        return ModuleInfo(info)


class ThreatIntelligenceModule(Module):
    """Base class for Threat Intelligence Modules"""

    def ioc_lookup(self, ioc):
        """To implement. Perform an IOC lookup to enrich analysis.

        Args:
            ioc (string): the IOC value to look for.

        Returns:
            A tuple (tags, indicators).

            tags is a list of tags (strings) that describe this IOC.

            indicators is a list of dicts with matching indicators, with the
            following keys:

                * ``name``: name of this indicator.
                * ``description``: additional description.
        """
        return [], []

    def iocs_submission(self, analysis, iocs):
        """To implement. Perform a bulk IOC submission.

        This method should send all IOCs selected by the analyst and send them
        to the Threat Intelligence Platform to enrich it.

        By default, this method calls
        :func:`fame.core.module.ThreatIntelligenceModule.ioc_submission` on
        every single IOC. This means that you should only define this method
        when you know how to do bulk submission. Otherwise, define
        :func:`fame.core.module.ThreatIntelligenceModule.ioc_submission`
        instead.

        Args:
            analysis: the analysis that generated the IOCs.
            iocs (list): a list of dicts with two keys: ``value`` (string
                containing the IOC's value) and ``tags`` (string containing a
                list of tags delimited with ``,``).
        """
        for ioc in iocs:
            self.ioc_submission(analysis, ioc['value'], ioc['tags'])

    def ioc_submission(self, analysis, ioc, tags):
        """To implement. Perform a single IOC submission.

        This method should send one IOC selected by the analyst and send it to
        the Threat Intelligence Platform to enrich it.

        It should only be defined when you don't know how to do bulk
        submission. Otherwise, define
        :func:`fame.core.module.ThreatIntelligenceModule.iocs_submission`
        instead.

        Args:
            analysis: the analysis that generated the IOC.
            ioc (string): the IOC's value.
            tags (string): a list of tags separated by ``,``.
        """
        pass

    @classmethod
    def static_info(cls):
        info = {
            "name": cls.name,
            "description": cls.description,
            "type": "Threat Intelligence",
            "config": cls.config,
            "diffs": {},
        }

        init_config_values(info)

        return ModuleInfo(info)


class AntivirusModule(Module):
    """Base class for Antivirus submission modules"""

    def submit(self, file):
        """To implement. Submit the file to an Antivirus vendor

        Args:
            file (string): full path of the file to submit.
        """
        pass

    @classmethod
    def static_info(cls):
        info = {
            "name": cls.name,
            "description": cls.description,
            "type": "Antivirus",
            "config": cls.config,
            "diffs": {},
        }

        init_config_values(info)

        return ModuleInfo(info)
