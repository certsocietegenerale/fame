import os
import ConfigParser
from StringIO import StringIO

from fame.common.constants import FAME_ROOT
from fame.common.objects import Dictionary


class ConfigObject:

    def __init__(self, filename=None, from_string=''):
        config = ConfigParser.SafeConfigParser({'root': FAME_ROOT}, allow_no_value=True)

        if filename:
            config.read(os.path.join(FAME_ROOT, "conf", "%s.conf" % filename))
        else:
            from_string = StringIO(from_string)
            config.readfp(from_string)
            from_string.close()

        for section in config.sections():
            setattr(self, section, Dictionary())
            for name in config.options(section):
                try:
                    value = config.getint(section, name)
                except ValueError:
                    try:
                        value = config.getboolean(section, name)
                    except ValueError:
                        value = config.get(section, name)

                getattr(self, section)[name] = value

    def get(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            return None


fame_config = ConfigObject(filename="fame").get('fame')
