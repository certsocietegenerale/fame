from copy import copy

from fame.common.objects import Dictionary
from fame.common.exceptions import MissingConfiguration
from fame.common.mongo_dict import MongoDict


def config_to_dict(config):
    result = {setting['name']: setting for setting in config}
    
    return result


# We will keep configured values, only if they have the same name and type
def apply_config_update(config, config_update):
    new_config = []
    config = config_to_dict(config)

    for setting in config_update:
        new_setting = copy(setting)

        if setting['name'] in config:
            if setting['type'] == config[setting['name']]['type']:
                new_setting['value'] = config[setting['name']]['value']
                if 'option' in config[setting['name']]:
                    new_setting['option'] = config[setting['name']]['option']

        new_config.append(new_setting)

    return new_config


def incomplete_config(config):
    for setting in config:
        if setting['value'] is None and 'default' not in setting:
            return True

    return False


# This is for FAME's internal configuration
class Config(MongoDict):
    collection_name = 'settings'

    def get_values(self):
        values = Dictionary()
        for setting in self['config']:
            if (setting['value'] is None) and ('default' not in setting):
                raise MissingConfiguration("Missing configuration value: {} (in '{}')".format(setting['name'], self['name']), self)

            values[setting['name']] = setting['value']
            if setting['value'] is None:
                values[setting['name']] = setting['default']

        return values

    def update_config(self, config):
        self['description'] = config['description']
        self['config'] = apply_config_update(self['config'], config['config'])
        self.save()
