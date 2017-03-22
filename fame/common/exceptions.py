class ModuleInitializationError(Exception):
    def __init__(self, module, description):
        self._module = module.name
        self._description = description

    def __str__(self):
        return "%s: %s" % (self._module, self._description)


class ModuleExecutionError(Exception):
    def __init__(self, description):
        self._description = description

    def __str__(self):
        return self._description


class MissingConfiguration(Exception):
    def __init__(self, description, config=None):
        self.name = None
        if config:
            self.name = config['name']
            self.id = config['_id']

        self._description = description

    def __str__(self):
        return self._description
