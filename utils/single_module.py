#! /usr/bin/env python

import os
import sys
import pkgutil
import inspect
import importlib
import datetime
import argparse

sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from utils import error, user_input
from fame.core import fame_init
from fame.common.objects import Dictionary
from fame.common.constants import MODULES_ROOT
from fame.common.utils import iterify, u
from fame.core.module import ProcessingModule
from fame.core.module_dispatcher import dispatcher


class Dispatcher:
    def __init__(self, interactive):
        self.modules = {}
        self.interactive = interactive

        for loader, name, ispkg in pkgutil.walk_packages([MODULES_ROOT], prefix='fame.modules.'):
            if not ispkg:
                try:
                    module = importlib.import_module(name)
                    for _, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, ProcessingModule):
                            if obj.name:
                                self.modules[obj.name] = obj
                except:
                    pass

    def get_processing_module(self, name):
        if name in self.modules:
            module = self.modules[name](with_config=False)
            module.info = module.static_info()
            self.init_config(module)

            return module

        return None

    def init_config(self, module):
        for named_config in module.named_configs:
            values = Dictionary()

            for setting in module.named_configs[named_config]['config']:
                if self.interactive or 'default' not in setting:
                    values[setting['name']] = self.get_value_from_user(setting, named_config)
                else:
                    values[setting['name']] = setting['default']

            setattr(module, named_config, values)

        for config in module.info['config']:
            if self.interactive or 'default' not in config:
                setattr(module, config['name'], self.get_value_from_user(config))
            else:
                setattr(module, config['name'], config['default'])

    def get_value_from_user(self, setting, prefix=None):
        if prefix:
            name = "{}.{}".format(prefix, setting['name'])
        else:
            name = setting['name']

        prompt = "{} ({})".format(name, setting['description'])
        if 'default' in setting:
            value = user_input(prompt, setting['default'])
        else:
            value = user_input(prompt)

        if setting['type'] == 'integer':
            value = int(value)
        elif setting['type'] == 'bool':
            value = bool(value)

        return value


class TestAnalysis(dict):
    def __init__(self, filename, file_type):
        self['filename'] = filename
        self['logs'] = []
        self['extractions'] = []
        self['generated_files'] = []
        self['extracted_files'] = []
        self['support_files'] = []
        self['probable_names'] = set()
        self['iocs'] = []
        self['options'] = {}

        self._file = {'type': file_type}
        self.file_type = file_type
        self.matched_type = False

    def log(self, level, message):
        self['logs'].append("%s: %s: %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), level, message))

    def filepath(self, path):
        return path

    def get_files(self, source_type):
        if self.file_type is None and not self.matched_type:
            self.matched_type = True
            return [self['filename']]
        elif self.file_type == source_type:
            return [self['filename']]
        else:
            return []

    def get_main_file(self):
        return self['filename']

    def change_type(self, location, new_type):
        print "Changing type of '{}' to '{}'".format(location, new_type)

    def add_extraction(self, label, extraction):
        self['extractions'].append({'label': label, 'content': u(extraction)})

    def add_generated_files(self, file_type, location):
        self['generated_files'].append({'type': file_type, 'path': location})

    def add_extracted_file(self, location):
        self['extracted_files'].append(location)

    def add_support_file(self, module, name, location):
        self['support_files'].append((module, name, location))

    def add_probable_name(self, probable_name):
        self['probable_names'].add(probable_name)

    def add_ioc(self, value, source, tags=[]):
        for ioc in self['iocs']:
            if ioc['value'] == value:
                break
        else:
            ioc = {'value': value, 'tags': set()}
            self['iocs'].append(ioc)

        for tag in iterify(tags):
            ioc['tags'].add(tag)

    def pprint(self):
        print "Probable Names: {}\n".format(", ".join(self['probable_names']))

        print "\n## Extracted Files\n"
        for f in self['extracted_files']:
            print "{}".format(f)

        print "\n## IOCs\n"
        for ioc in self['iocs']:
            print "{} ({})".format(ioc['value'], ", ".join(ioc['tags']))

        print "\n## Extractions\n"
        for extraction in self['extractions']:
            print "-- {} --\n\n{}".format(extraction['label'], extraction['content'])

        print "\n## Generated Files\n"
        for f in self['generated_files']:
            print "{} ({})".format(f['path'], f['type'])

        print "\n## Support Files\n"
        for f in self['support_files']:
            print "{}".format(f)

        print "\n## Logs\n"
        for f in self['logs']:
            print "\n".join(self['logs'])


def test_mode_module(name, interactive):
    print "[+] Enabling test mode."
    dispatcher = Dispatcher(interactive)
    module = dispatcher.get_processing_module(name)

    if module:
        module.initialize()
    else:
        error("Could not find module '{}'".format(name))

    return module


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Launches a single FAME module.')
    parser.add_argument('module', metavar='module', type=str,
                        help='The name of the module to run.')
    parser.add_argument('file', metavar='file', type=str,
                        help='The file to analyze.')
    parser.add_argument('type', metavar='type', type=str, nargs="?",
                        help='The FAME type to use for this file.')
    parser.add_argument('-i', '--interactive', action='store_true',
                        help='Ask the user for every configuration option. Without this option, it will use default values when provided. Only used in test mode.')
    parser.add_argument('-t', '--test', action='store_true',
                        help='Enable test mode. This mode does not require connection to the database. It is automatically enabled when a connection is not available or the module is disabled.')

    args = parser.parse_args()

    analysis = TestAnalysis(args.file, args.type)

    if args.test:
        module = test_mode_module(args.module, args.interactive)
    else:
        try:
            fame_init()
            module = dispatcher.get_processing_module(args.module)
            module.initialize()
        except:
            module = test_mode_module(args.module, args.interactive)

    ret = module.execute(analysis)

    print "\nResult: {}\n".format(ret)

    analysis.pprint()

    if module.results is not None:
        print "## Detailed results\n"
        print module.results
