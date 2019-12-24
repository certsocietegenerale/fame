import fnmatch
import inspect
import pkgutil
import importlib
from os import path, walk, remove
from collections import OrderedDict

from fame.common.utils import get_class, iterify, unique_for_key
from fame.core.config import Config, incomplete_config
from fame.core.module import Module, ModuleInfo


class DispatchingException(Exception):
    pass


class ModuleDispatcher(object):
    def reload(self):
        self._modules = {
            'Preloading': [],
            'Processing': {},
            'Reporting': [],
            'Antivirus': [],
            'Threat Intelligence': [],
            'Virtualization': [],
            'Filetype': {}
        }
        self._direct_transforms = {}
        self._transforms = {}
        self._triggers = {}
        self._dynamic_triggers = {}
        self._general = []
        self.options = {
            'str': {},
            'text': {},
            'integer': {},
            'bool': {}
        }
        self.permissions = OrderedDict([
            ('*', 'This special permission means all permissions.'),
            ('manage_modules', 'Allows for module operations (installation, configuration, etc.)'),
            ('manage_users', 'Allows for users management (creation, modification, etc.)'),
            ('configs', 'Grants access to the "Configs" section that tracks malware configurations.'),
            ('submit_iocs', 'Allows user to send observables to Threat Intelligence modules.'),
            ('add_probable_name', "Allows user to set an object's probable name"),
            ('see_logs', 'Allows user to access the log section of anlyses. This could reveal information on the underlying system.')
        ])

        self.load_all_modules()

    def get_module(self, module_name):
        return (
            self.get_preloading_module(module_name) or
            self.get_processing_module(module_name) or
            None
        )

    def get_processing_module(self, module_name):
        if module_name in self._modules['Processing']:
            return self._modules['Processing'][module_name]()

        return None

    def get_preloading_module(self, module_name):
        for module in self._modules['Preloading']:
            if module.info['name'] == module_name:
                return module()
        else:
            return None

    # Get all modules triggered by a specific tag
    def triggered_by(self, tag):
        results = []

        if tag in self._triggers:
            results = results + self._triggers[tag]

        for trigger in self._dynamic_triggers:
            if fnmatch.fnmatch(tag, trigger):
                results = results + self._dynamic_triggers[trigger]

        return results

    # Get next module to execute to achieve some goal
    def next_module(self, types_available, module_name, excluded_modules):
        module = self.get_processing_module(module_name)

        if module is None:
            raise DispatchingException("Could not find execution path")

        if not module.info['acts_on']:
            return module_name
        else:
            for acts_on in iterify(module.info['acts_on']):
                if acts_on in types_available:
                    return module_name
            else:
                return self._shortest_path_to_module(types_available, module, excluded_modules)

    def get_next_preloading_module(self, excluded_modules=[]):
        candidate_modules = []

        for module in self.get_preloading_modules():
            if module.info['name'] not in excluded_modules:
                candidate_modules.append(module.info['name'])

        if len(candidate_modules) > 0:
            return candidate_modules[0]
        else:
            return ""

    # Get all generale purpose modules
    def general_purpose(self):
        return self._general

    def get_reporting_modules(self):
        return self._modules['Reporting']

    def get_threat_intelligence_modules(self):
        return self._modules['Threat Intelligence']

    def get_antivirus_modules(self):
        return self._modules['Antivirus']

    def get_preloading_modules(self):
        return self._modules['Preloading']

    def get_filetype_modules_for(self, current_type):
        if current_type in self._modules['Filetype']:
            return self._modules['Filetype'][current_type]
        else:
            return []

    def get_virtualization_module(self, name):
        for m in self._modules['Virtualization']:
            if m.name == name and m.info['enabled']:
                return m()

        return None

    def add_module(self, module):
        m = get_class(module['path'], module['class'])
        if m:
            m.info = module
            try:
                m = m()
                if m and m.initialize():
                    self._modules[module['type']].append(m)
            except Exception, e:
                print "Could not initialize module '{0}': {1}".format(module['name'], e)

    def add_virtualization_module(self, module):
        m = get_class(module['path'], module['class'])

        if m:
            m.info = module
            self._modules['Virtualization'].append(m)

    def add_filetype_module(self, module):
        def add_one(acts_on, module):
            if acts_on not in self._modules['Filetype']:
                self._modules['Filetype'][acts_on] = []

            self._modules['Filetype'][acts_on].append(module)

        m = get_class(module['path'], module['class'])

        if m:
            m.info = module
            try:
                m = m()
                if m and m.initialize():
                    if len(module['acts_on']) == 0:
                        add_one('*', m)
                    else:
                        for acts_on in module['acts_on']:
                            add_one(acts_on, m)
            except Exception, e:
                print "Could not initialize module '{0}': {1}".format(module['name'], e)

    def add_processing_module(self, module):
        m = get_class(module['path'], module['class'])
        if m:
            m.info = module
            self._modules['Processing'][module['name']] = m

            self._add_module_options(module)
            self._add_module_permissions(module)

            # Add module to transform if 'generates' is defined
            if module['generates']:
                self._add_transforms(module)

            # Add module to triggers if 'triggered_by' is defined
            if module['triggered_by']:
                self._add_module_triggers(module)
            # Otherwise, add to general purpose modules
            else:
                self._general.append(module['name'])
                # Also, if module acts on specific file type, add a specific trigger
                if module['acts_on']:
                    for source_type in iterify(module['acts_on']):
                        self._add_trigger(self._triggers, "_generated_file(%s)" % source_type, module)

    def add_preloading_module(self, module):
        m = get_class(module['path'], module['class'])
        if m:
            m.info = module
            self._add_module_options(module)
            self._modules['Preloading'].append(m)

    def _add_module_permissions(self, module):
        module = self._modules['Processing'][module['name']]
        for permission in module.permissions:
            self.permissions[permission] = module.permissions[permission]

    def _add_module_options(self, module):
        for config in module['config']:
            if 'option' in config and config['option']:
                if config['name'] not in self.options[config['type']]:
                    self.options[config['type']][config['name']] = {
                        'default': config['value'] or (config['default'] if 'default' in config else None),
                        'display': config['display'] if 'display' in config else config['name'],
                        'description': config['description'],
                        'modules': []
                    }

                self.options[config['type']][config['name']]['modules'].append(module['name'])

    def _add_trigger(self, trigger_list, trigger, module):
        # Add trigger if not already present
        if trigger not in trigger_list:
            trigger_list[trigger] = []

        # Add module to defined trigger
        trigger_list[trigger].append(module['name'])

    def _add_module_triggers(self, module):
        for trigger in iterify(module['triggered_by']):
            if '*' in trigger or '?' in trigger or '[' in trigger:
                self._add_trigger(self._dynamic_triggers, trigger, module)
            else:
                self._add_trigger(self._triggers, trigger, module)

    def _add_transforms(self, module):
        if not module['acts_on']:
            for generated_type in iterify(module.generates):
                if generated_type not in self._direct_transforms:
                    self._direct_transforms[generated_type] = []
                self._direct_transforms[generated_type].append(module['name'])
        else:
            for source_type in iterify(module['acts_on']):
                if source_type not in self._transforms:
                    self._transforms[source_type] = []

                for generated_type in iterify(module['generates']):
                    self._transforms[source_type].append({'type': generated_type, 'module': module['name']})

    def load_all_modules(self):
        for module in ModuleInfo.get_collection().find({'enabled': True}):
            if module['type'] == "Processing":
                self.add_processing_module(module)
            elif module['type'] == "Virtualization":
                self.add_virtualization_module(module)
            elif module['type'] == "Filetype":
                self.add_filetype_module(module)
            elif module['type'] == "Preloading":
                self.add_preloading_module(module)
            else:
                self.add_module(module)

    def update(self, module, path, repository):
        named_configs = []

        if module.name:
            module_info = ModuleInfo.get(name=module.name)

            # Ignore duplicates
            if module_info and not module_info['path'].startswith('fame.modules.{}.'.format(repository['name'])):
                print "Duplicate name '{}', ignoring module.".format(module.name)
                return None

            # Handle named configs
            for named_config in module.named_configs:
                config = Config.get(name=named_config)

                # Creation
                if config is None:
                    config = Config(module.named_config(named_config))
                    config.save()
                # Update
                else:
                    config.update_config(module.named_config(named_config))

                named_configs.append(config)

            # Handle module info
            if module_info is None:
                module_info = module.static_info()
                module_info['enabled'] = False
            else:
                module_info.update_config(module.static_info())

            module_info['class'] = module.__name__
            module_info['path'] = path
            module_info.save()

        return named_configs

    def list_installed_modules_for(self, repository):
        results = set()

        for module in ModuleInfo.get_collection().find():
            if module['path'].startswith('fame.modules.{}.'.format(repository['name'])):
                results.add(module['name'])

        return results

    def _remove_compiled_files(self, root_dir):
        for root, dirs, files in walk(root_dir):
            for f in files:
                if f.endswith('.pyc'):
                    remove(path.join(root, f))

    def walk_modules(self, modules_dir, repository=None):
        for loader, name, ispkg in pkgutil.walk_packages([modules_dir], prefix='fame.modules.'):
            if not ispkg:
                if repository is None or name.startswith('fame.modules.{}.'.format(repository['name'])):
                    try:
                        module = importlib.import_module(name)
                        for _, obj in inspect.getmembers(module, inspect.isclass):
                            if issubclass(obj, Module):
                                yield name, obj
                    except ImportError:
                        pass

    def update_modules(self, repository):
        base_dir = path.dirname(path.dirname(path.abspath(__file__)))
        modules_dir = path.join(base_dir, 'modules')

        self._remove_compiled_files(modules_dir)

        installed_modules = self.list_installed_modules_for(repository)
        updated_named_configs = []

        for name, obj in self.walk_modules(modules_dir, repository=repository):
            updated_named_configs += self.update(obj, name, repository)

            if obj.name:
                installed_modules.discard(obj.name)

        # Delete all modules that are no longer in the repository
        for missing_module in installed_modules:
            print "Deleting '{}'".format(missing_module)
            ModuleInfo.get_collection().remove({'name': missing_module})

        # Disable all modules that have incomplete named configs
        for updated_named_config in unique_for_key(updated_named_configs, 'name'):
            if incomplete_config(updated_named_config['config']):
                for name, obj in self.walk_modules(modules_dir):
                    if obj.name and updated_named_config['name'] in obj.named_configs:
                        info = ModuleInfo.get(name=obj.name)

                        if info['enabled']:
                            print "Disabling {} for incomplete named config {}".format(obj.name, updated_named_config['name'])
                            info.update_value('enabled', False)

    # Return the first direct transform that is not in the excluded modules
    def _get_direct_transform(self, destination_type, excluded_modules):
        if destination_type in self._direct_transforms:
            for module in self._direct_transforms[destination_type]:
                if module not in excluded_modules:
                    return module

        return None

    def _shortest_path_to_module(self, types_available, target_module, excluded_modules):
        next_module = None
        path_length = None

        for destination_type in iterify(target_module.info['acts_on']):
            module, length = self._shortest_path_to_type(types_available, destination_type, excluded_modules + [target_module.info['name']])
            if path_length is None or length < path_length:
                path_length = length
                next_module = module

        if path_length is None:
            raise DispatchingException("Could not find execution path")
        else:
            return next_module

    # Return the shortest path to a specific type
    #
    # Resolution order:
    #   1. Regular transform with a path length of 1
    #   2. Direct transform
    #   3. Regular transform with a path length > 1
    def _shortest_path_to_type(self, types_available, destination_type, excluded_modules):
        next_module = None
        path_length = None

        for source_type in types_available:
            module, length = self._shortest_path(source_type, destination_type, excluded_modules)
            if path_length is None or length < path_length:
                path_length = length
                next_module = module

        if path_length == 1:
            return (next_module, 1)
        else:
            direct_transform = self._get_direct_transform(destination_type, excluded_modules)
            if direct_transform:
                return (direct_transform, 1)
            else:
                return (next_module, path_length)

    def _shortest_path(self, source_type, destination_type, excluded_modules, excluded_types=None):
        next_module = None
        path_length = None

        if excluded_types is None:
            excluded_types = []

        excluded_types.append(source_type)

        if source_type in self._transforms:
            for transform in self._transforms[source_type]:
                if transform['module'] not in excluded_modules:
                    length = self._path_length_from_module(transform, destination_type, excluded_modules, excluded_types)
                    if (length is not None) and (path_length is None or length < path_length):
                        path_length = length
                        next_module = transform['module']

        return (next_module, path_length)

    def _path_length_from_module(self, transform, destination_type, excluded_modules, excluded_types):
        if transform['type'] in excluded_types:
            return None
        elif transform['type'] == destination_type:
            return 1
        else:
            module, length = self._shortest_path(transform['type'], destination_type, excluded_modules, excluded_types)
            if length is not None:
                return length + 1
            else:
                return None


dispatcher = ModuleDispatcher()
