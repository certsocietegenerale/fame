import os
import inspect
import requests
import traceback
from time import sleep
from urlparse import urljoin
from markdown2 import markdown
from datetime import datetime, timedelta

from fame.common.constants import MODULES_ROOT
from fame.common.exceptions import ModuleInitializationError, ModuleExecutionError, MissingConfiguration
from fame.common.utils import iterify, is_iterable, list_value, save_response, ordered_list_value
from fame.common.mongo_dict import MongoDict
from fame.core.config import Config, apply_config_update, incomplete_config
from fame.core.internals import Internals


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

    def get_readme(self):
        readme = self.get_file('README.md')

        if readme:
            with open(readme, 'r') as f:
                readme = markdown(f.read(), extras=["code-friendly"])

        return readme

    def details_template(self):
        return '/'.join(self['path'].split('.')[2:-1]) + '/details.html'

    def update_config(self, new_info):
        def _update_queue():
            self['queue'] = new_info['queue']
            if 'queue' in self['diffs']:
                if self['diffs']['queue'] == new_info['queue']:
                    del self['diffs']['queue']
                else:
                    self['queue'] = self['diffs']['queue']

        if self['type'] == 'Processing':
            self['generates'] = new_info['generates']
            _update_queue()
            self._update_diffed_value('acts_on', new_info['acts_on'])
            self._update_diffed_value('triggered_by', new_info['triggered_by'])

        elif self['type'] == 'Preloading':
            _update_queue()

        elif self['type'] == 'Filetype':
            self._update_diffed_value('acts_on', new_info['acts_on'])

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

            setattr(self, config['name'], config['value'])
            if config['value'] is None:
                setattr(self, config['name'], config['default'])

    def log(self, level, message):
        """Add a log message to the analysis

        Args:
            level: string to define the log level (``debug``, ``info``, ``warning`` or ``error``).
            message: free text message containing the log information.
        """
        self._analysis.log(level, "%s: %s" % (self.name, message))

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

    def add_extracted_file(self, location, automatic_analysis=True):
        """Create a new file that deserves its own analysis.

        Args:
            location (string): full path."""
        self._analysis.add_extracted_file(location, automatic_analysis)

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


class IsolatedProcessingModule(ProcessingModule):
    """Base class for isolated processing modules.

    All processing modules that needs to be executed in an isolated environment
    (a VM) should inherit from this class.

    Instead of executing the module directly, the worker will orchestrate a
    specifically configured Virtual Machine and execute the module inside of it.

    Attributes:
        should_restore: A boolean that can be set by the module to indicate that
            the VM should be restored to a clean state. It is set to ``False`` by
            default.
    """
    vm_config = [
        {
            'name': 'virtualization',
            'type': 'str',
            'default': 'virtualbox',
            'description': 'Name of the VirtualizationModule to use.'
        },
        {
            'name': 'label',
            'type': 'str',
            'description': 'Label of the virtual machine to use. Several VMs can be specified by using a comma-delimited list of labels.'
        },
        {
            'name': 'snapshot',
            'type': 'str',
            'default': None,
            'description': 'Name of the snapshot to use to restore clean state.'
        },
        {
            'name': 'ip_address',
            'type': 'str',
            'default': '127.0.0.1',
            'description': 'IP address of the guest. 127.0.0.1 can only be used with NAT and port forwarding. When using muliple VMs, specify all IP addresses in a comma-delimited list.'
        },
        {
            'name': 'port',
            'type': 'str',
            'default': '4242',
            'description': 'Port the agent is listening to. You might have to change this value if you are using NAT and port forwarding. When using muliple VMs, specify all ports in a comma-delimited list.'
        },
        {
            'name': 'always_ready',
            'type': 'bool',
            'default': True,
            'description': 'Make sure the VM is always started and ready to execute a new task.'
        },
        {
            'name': 'restore_after',
            'type': 'integer',
            'default': 10,
            'description': 'Only used when always_ready is used. Specifies the number of times this module can be executed before having to clean up the virtual machine.'
        }
    ]

    def initialize(self):
        self.task_id = None
        self.should_restore = False

        self.labels = ordered_list_value(self.label)
        self.ip_addresses = ordered_list_value(self.ip_address)
        self.ports = ordered_list_value(self.port)

        if not (len(self.labels) == len(self.ip_addresses) == len(self.ports)):
            raise ModuleInitializationError(self, "List values for 'label', 'ip_address' and 'port' must contain exactly the same number of elements.")

    def __init__(self, with_config=True):
        ProcessingModule.__init__(self, with_config)

        setattr(self.__class__, 'initialize', IsolatedProcessingModule.initialize)
        setattr(self.__class__, 'each_with_type', IsolatedProcessingModule.each_with_type)

    def _url(self, path):
        if self.task_id:
            return urljoin(self.base_url, "/{}{}".format(self.task_id, path))
        else:
            return urljoin(self.base_url, path)

    def _make_request(self, method, path, **kwargs):
        try:
            url = self._url(path)

            if method == "GET":
                response = requests.get(url, **kwargs)
            else:
                response = requests.post(url, **kwargs)

            response.raise_for_status()

            return response
        except Exception, e:
            raise ModuleExecutionError("Error communicating with agent ({}): {}".format(path, e))

    def _get(self, path, **kwargs):
        return self._make_request("GET", path, **kwargs).json()

    def _post(self, path, **kwargs):
        return self._make_request("POST", path, **kwargs).json()

    def _new_task(self):
        response = self._get('/new_task')
        self.task_id = response['task_id']

        if self.task_id is None:
            raise ModuleExecutionError("Could not get valid task id.")

    def _get_config(self):
        result = {}

        for setting in self.config:
            result[setting['name']] = getattr(self, setting['name'])

        return result

    def _send_module(self):
        fd = open(inspect.getsourcefile(self.__class__))
        result = self._post('/module_update', files={'file': fd})
        fd.close()

        result = self._post('/module_update_info', json={'name': self.name, 'config': self._get_config()})

        if result['status'] != 'ok':
            raise ModuleInitializationError(self, result['error'])

    def _get_file(self, filepath):
        response = self._make_request('POST', '/get_file', data={'filepath': filepath}, stream=True)

        return save_response(response)

    def _get_results(self):
        results = self._get('/results')

        self.results = results['results']
        self.should_restore = results['should_restore']
        self.tags = results['_results']['tags']

        for level, message in results['_results']['logs']:
            self.log(level, message)

        for name in results['_results']['probable_names']:
            self.add_probable_name(name)

        for extraction in results['_results']['extractions']:
            self.add_extraction(extraction, results['_results']['extractions'][extraction])

        for ioc in results['_results']['iocs']:
            self.add_ioc(ioc, results['_results']['iocs'][ioc])

        for file_type in results['_results']['generated_files']:
            local_files = []

            for remote_file in results['_results']['generated_files'][file_type]:
                local_files.append(self._get_file(remote_file))

            self.register_files(file_type, local_files)

        for f in results['_results']['extracted_files']:
            self.add_extracted_file(self._get_file(f))

        for name in results['_results']['support_files']:
            self.add_support_file(name, self._get_file(results['_results']['support_files'][name]))

        return results['_results']['result']

    def _use_vm(self, index):
        self.locked_label = self.labels[index]
        self.base_url = "http://{}:{}".format(self.ip_addresses[index], self.ports[index])
        self.vm_record = "{}|{}".format(self.virtualization, self.locked_label)

    def _acquire_lock(self):
        LOCK_TIMEOUT = timedelta(minutes=120)
        WAIT_STEP = 15

        vms = Internals.get(name='virtual_machines')

        if vms is None:
            vms = Internals({'name': 'virtual_machines'})
            vms.save()

        locked_vm = False
        while not locked_vm:
            for i, label in enumerate(self.labels):
                self._use_vm(i)

                last_locked = "{}.last_locked".format(self.vm_record)

                if vms.update_value([self.vm_record, 'locked'], True):
                    vms.update_value([self.vm_record, 'last_locked'], datetime.now())
                    locked_vm = True
                    break

                expired_date = datetime.now() - LOCK_TIMEOUT
                if vms._update({'$set': {last_locked: datetime.now()}},
                               {last_locked: {'$lt': expired_date}}):
                    vms.update_value([self.vm_record, 'locked'], True)
                    locked_vm = True
                    break

            if not locked_vm:
                sleep(WAIT_STEP)

    def _release_lock(self):
        vms = Internals.get(name='virtual_machines')
        vms.update_value([self.vm_record, 'locked'], False)

    def _init_vm(self):
        from fame.core.module_dispatcher import dispatcher
        self._vm = dispatcher.get_virtualization_module(self.virtualization)

        if self._vm is None:
            raise ModuleExecutionError('missing (or disabled) virtualization module: {}'.format(self.virtualization))

        self._vm.initialize(self.locked_label, self.base_url, self.snapshot)
        self._vm.prepare()

    def _restore_vm(self):
        if self.always_ready:
            vms = Internals.get(name='virtual_machines')

            if self.name not in vms[self.vm_record]:
                vms.update_value([self.vm_record, self.name], 1)
            else:
                vms.update_value([self.vm_record, self.name], vms[self.vm_record][self.name] + 1)

            if vms[self.vm_record][self.name] >= self.restore_after:
                self.should_restore = True

            if self.should_restore:
                self._vm.restore()
                vms.update_value([self.vm_record, self.name], 0)
        else:
            self._vm.stop()

    def run(self):
        # Make sure no other module will use this VM before we are done
        self._acquire_lock()

        try:
            # Make sure the VM is ready
            self._init_vm()

            # Launch the module on the agent
            self._new_task()
            self._send_module()
            ProcessingModule.run(self)
            result = self._get_results()
            self._restore_vm()

            return result
        finally:
            # Release the virtual machine
            self._release_lock()

        return True

    def each_with_type(self, target, target_type):
        # First, send target and start processing
        kwargs = {}

        if target_type == 'url':
            kwargs['data'] = {'url': target}
        else:
            fd = open(target, 'rb')
            kwargs['files'] = {'file': fd}

        self._post('/module_each/{}'.format(target_type), **kwargs)

        if target_type != 'url':
            fd.close()

        # Then, wait for processing to be over
        ready = self._get('/ready')['ready']
        while not ready:
            sleep(5)
            ready = self._get('/ready')['ready']

    @classmethod
    def static_info(cls):
        info = {
            "name": cls.name,
            "description": cls.description,
            "type": "Processing",
            "config": cls.vm_config + cls.config,
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

    def has_submit_implementation(self):
        """
        This method checks if one of the submission methods has been
        overwritten from his origin class.

        This way, you can know if the ThreatIntelligence module has submission
        capability.
        """
        methods = [self.iocs_submission, self.ioc_submission]
        for method in methods:
            for cls in inspect.getmro(method.im_class):
                if method.__name__ in cls.__dict__:
                    if cls.__name__ != 'ThreatIntelligenceModule':
                        return True
        return False


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


class FiletypeModule(Module):
    """Base class for Filetype Modules"""

    acts_on = []

    def recognize(self, filepath, current_type):
        """To implement. Checks the file in order to determine more accurate
        type.

        Args:
            filepath (string): full path of the file to analyze.
            current_type (string): the file's current type.

        Returns:
            The name of the FAME type that was recognized (string), or None.
        """
        pass

    @classmethod
    def static_info(cls):
        info = {
            "name": cls.name,
            "description": cls.description,
            "acts_on": iterify(cls.acts_on),
            "type": "Filetype",
            "config": cls.config,
            "diffs": {},
        }

        init_config_values(info)

        return ModuleInfo(info)


class VirtualizationModule(Module):
    """Base class for Virtualization modules, used by IsolatedProcessingModules"""

    TIMEOUT = 120

    def initialize(self, vm, base_url, snapshot=None):
        """To implement if you have to check for requirements.

        If you define your own implementation, you should make sure to call the
        base one::

            VirtualizationModule.initialize(self, vm, base_url, snapshot)

        Args:
            vm (string): label associated with the VM to use.
            base_url (string): base URL for the web service.
            snapshot (string): name of the snapshot to use when restoring the VM.

        Raises:
            ModuleInitializationError: One of requirements was not met.
        """
        self.vm_label = vm
        self.snapshot = snapshot

        self.agent_url = "{}/ready".format(base_url)

    def is_running(self):
        """To implement.

        Must return ``True`` if the VM ``self.vm_label`` is in a running state.

        Raises:
            ModuleExecutionError: Could not execute correctly.
        """
        raise NotImplementedError

    def restore_snapshot(self):
        """To implement.

        Restore the snapshot in ``self.snapshot``. When ``None``, should restore
        the current snapshot.

        Raises:
            ModuleExecutionError: Could not execute correctly.
        """
        raise NotImplementedError

    def start(self):
        """To implement.

        Start the VM ``self.vm_label``.

        Raises:
            ModuleExecutionError: Could not execute correctly.
        """
        raise NotImplementedError

    def stop(self):
        """To implement.

        Stop the VM ``self.vm_label``.

        Raises:
            ModuleExecutionError: Could not execute correctly.
        """
        raise NotImplementedError

    def is_ready(self):
        try:
            r = requests.get(self.agent_url, timeout=1)

            return r.status_code == 200
        except:
            return False

    def restore(self, should_raise=True):
        if self.is_running():
            self.stop()

        self.restore_snapshot()

        if not self.is_running():
            self.start()

        started_at = datetime.now()
        while (started_at + timedelta(seconds=self.TIMEOUT) > datetime.now()):
            if self.is_ready():
                break
            sleep(5)
        else:
            if should_raise:
                raise ModuleExecutionError("could not restore virtual machine '{}' before timeout.".format(self.vm_label))

    def prepare(self):
        if not (self.is_running() and self.is_ready()):
            self.restore()

    @classmethod
    def static_info(cls):
        info = {
            "name": cls.name,
            "description": cls.description,
            "type": "Virtualization",
            "config": cls.config,
            "diffs": {},
        }

        init_config_values(info)

        return ModuleInfo(info)


class PreloadingModule(Module):
    """ PreloadingModules can be used to download the sample
        binary from e.g. VirusTotal before queueing any
        processing modules. Hence, PreloadingModules only work
        on hashes. A successful execution of a PreloadingModule
        updates the Analysis object with the new data and queues
        the remaining modules as if the sample itself was uploaded
        the FAME.
    """

    queue = 'unix'

    def __init__(self, with_config=True):
        Module.__init__(self, with_config)
        self.results = None
        self.tags = []

    def preload(self, target):
        """ To implement.

        Args:
            target (string): the hash that is to be analyzed
        Raises:
            ModuleExecutionError: Preloading the analysis failed (e.g.
                                  no file for a given hash was found).
        """
        raise NotImplementedError

    def add_preloaded_file(self, filepath, fd):
        self._analysis.add_preloaded_file(filepath, fd)

    def init_options(self, options):
        for option in options:
            setattr(self, option, options[option])

    def execute(self, analysis):
        self._analysis = analysis
        self.init_options(analysis['options'])
        return self.preload(self._analysis.get_main_file())

    @classmethod
    def static_info(cls):
        info = {
            "name": cls.name,
            "description": cls.description,
            "type": "Preloading",
            "config": cls.config,
            "diffs": {},
            "queue": cls.queue
        }

        init_config_values(info)

        return ModuleInfo(info)
