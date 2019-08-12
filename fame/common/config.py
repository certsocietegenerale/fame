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

    @classmethod
    def from_env(cls):
        config = Dictionary()
        config['mongo_host'] = os.getenv("MONGO_HOST", "localhost")
        config['mongo_port'] = int(os.getenv("MONGO_PORT", "27017"))
        config['mongo_db'] = os.getenv("MONGO_DB", "fame")
        config['mongo_user'] = os.getenv("MONGO_USERNAME", "")
        config['mongo_password'] = os.getenv("MONGO_PASSWORD", "")
        config['auth'] = 'user_password'

        config['fame_url'] = os.getenv("FAME_URL", "http://localhost/")
        config['is_worker'] = os.getenv("FAME_WORKER", "0")

        config['storage_path'] = os.getenv("FAME_STORAGE_PATH", "{root:s}/storage").format(root=FAME_ROOT)
        config['temp_path'] = os.getenv("FAME_TEMP_PATH", "{root:s}/temp").format(root=FAME_ROOT)
        config['secret_key'] = os.getenv("FAME_SECRET_KEY", "")

        return config


def get_fame_config():
    docker = (os.getenv("FAME_DOCKER") == "1")
    if docker:
        fame_config = ConfigObject.from_env()
    else:
        fame_config = ConfigObject(filename="fame").get('fame')

    if fame_config is None:
        fame_config = Dictionary()
        fame_config['mongo_host'] = 'localhost'
        fame_config['mongo_port'] = 27017
        fame_config['mongo_db'] = 'fame'
        fame_config['auth'] = 'user_password'

    return fame_config


fame_config = get_fame_config()
