import os
import requests
from base64 import b64encode

from fame.core.store import store
from fame.common.utils import delete_from_disk
from fame.common.constants import AVATARS_ROOT
from fame.common.mongo_dict import MongoDict


class FilteredCollection():
    def __init__(self, collection, filters):
        self.collection = collection
        self.filters = filters

    def find(self, filters={}):
        combined_filters = filters.copy()
        combined_filters.update(self.filters)
        return self.collection.find(combined_filters)

    def find_one(self, filters={}):
        combined_filters = filters.copy()
        combined_filters.update(self.filters)
        return self.collection.find_one(combined_filters)

    def count_documents(self, filters={}):
        combined_filters = filters.copy()
        combined_filters.update(self.filters)
        return self.collection.count_documents(combined_filters)

class User(MongoDict):
    collection_name = 'users'

    def __init__(self, values):
        self['permissions'] = []
        self['api_key'] = User.generate_api_key()
        MongoDict.__init__(self, values)

        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
        self.is_api = False

        self.files = FilteredCollection(store.files, self.filters())
        self.analyses = FilteredCollection(store.analysis, self.filters())

    def get_id(self):
        return self['auth_token']

    def filters(self):
        if '*' in self['groups']:
            return {}
        else:
            return {'groups': {'$in': self['groups']}}

    def has_permission(self, permission):
        return (permission in self['permissions']) or ('*' in self['permissions'])

    def generate_avatar(self):
        s = b64encode(os.urandom(64))
        try:
            response = requests.get("https://robohash.org/{}.png".format(s))
            response.raise_for_status()
            with open(os.path.join(AVATARS_ROOT, "{}.png".format(self['_id'])), 'wb') as f:
                f.write(response.content)
        except:
            print(("Could not generate avatar for {}".format(self['email'])))

    def delete(self):
        delete_from_disk(os.path.join(AVATARS_ROOT, "{}.png".format(self['_id'])))
        super().delete()

    @staticmethod
    def generate_api_key():
        return os.urandom(40).hex()
