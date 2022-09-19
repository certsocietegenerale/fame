import os
import sys
import platform
from urllib.parse import quote_plus
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import OperationFailure

try:
    from importlib.metadata import distribution
except ImportError:
    from importlib_metadata import distribution

sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from fame.common.config import fame_config  # noqa: E402
from fame.core.config import Config, incomplete_config  # noqa: E402
from fame.core.module import ModuleInfo  # noqa: E402
from fame.core import fame_init  # noqa: E402


def version_info():
    print("########## VERSION ##########\n")
    print(("OS: {}".format(platform.version())))
    print(("Python: {}".format(platform.python_version())))
    print("\n")


def dependencies():
    print("########## DEPENDENCIES ###########\n")
    pipmain = distribution("pip").entry_points[0].load()

    pipmain(['freeze'])
    print("\n")


def test_mongodb_connection(db):
    try:
        test_collection = Collection(db, "auth_check", create=True)
        test_collection.drop()
        return True
    except OperationFailure:
        return False


def mongodb():
    print("########## MongoDB ##########\n")

    try:
        connection = MongoClient(fame_config.mongo_host, int(fame_config.mongo_port), serverSelectionTimeoutMS=10000)
        db = connection[fame_config.mongo_db]

        if fame_config.mongo_user and fame_config.mongo_password:
            db.authenticate(fame_config.mongo_user, quote_plus(fame_config.mongo_password), mechanism='SCRAM-SHA-1')

        print(("Version: {}".format(connection.server_info()['version'])))
        print(("Authorization check: {}\n".format(test_mongodb_connection(db))))
        return True
    except Exception as e:
        print(("Could not connect to MongoDB: {}\n".format(e)))
        return False


def configuration():
    print("########## Configuration ##########\n")
    fame_init()
    for config in Config.find():
        print(("{}: {}".format(config['name'], not incomplete_config(config['config']))))

    print("\nModules:\n")

    for module in ModuleInfo.find():
        state = "Disabled"
        configured = "Configured"

        if module['enabled']:
            state = "Enabled"

        if incomplete_config(module['config']):
            configured = "Not Configured"

        print(("{: <25} {: <20} {: <10} {: <15}".format(module['name'], module['type'], state, configured)))


def main():
    version_info()
    dependencies()
    if mongodb():
        configuration()


if __name__ == '__main__':
    main()
