from pymongo import TEXT, MongoClient

from fame.common.config import fame_config


class Store:
    def __init__(self):
        self.init()

    def init(self):
        # Connection
        if fame_config.mongo_user and fame_config.mongo_password:
            self._con = MongoClient(host=fame_config.mongo_host,
                port=int(fame_config.mongo_port),
                serverSelectionTimeoutMS=10000,
                username=fame_config.mongo_user,
                password=fame_config.mongo_password,
                authSource=fame_config.mongo_db,
                unicode_decode_error_handler='replace')
        else:
            self._con = MongoClient(host=fame_config.mongo_host,
                port=int(fame_config.mongo_port),
                serverSelectionTimeoutMS=10000,
                unicode_decode_error_handler='replace')
        self.db = self._con[fame_config.mongo_db]

        # Collections
        self.files = self.db.files
        self.analysis = self.db.analysis
        self.users = self.db.users
        self.modules = self.db.modules

        # This part is for malware configuration tracking ("the 'Configs' tab")
        self.configs = self.db.configs
        self.config_blocks = self.db.config_blocks

        # This is for FAME's configuration
        self.settings = self.db.settings
        self.repositories = self.db.repositories
        self.internals = self.db.internals

    def connect(self):
        self.init()

        # Create indexes
        self.files.create_index("md5")
        self.files.create_index("sha1")
        self.files.create_index("sha256")
        self.files.create_index([("$**", TEXT)], background=True)
        self.analysis.create_index("date")
        self.analysis.create_index([("$**", TEXT)], background=True)

    def collection(self, name):
        return self.db[name]


store = Store()
