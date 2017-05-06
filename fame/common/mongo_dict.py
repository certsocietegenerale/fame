import collections

from fame.common.utils import iterify
from fame.core.store import store


class MongoDict(dict):
    # Should be defined for children classes
    # ex: collection_name = 'files'
    collection_name = None

    def __init__(self, values={}):
        dict.__init__(self, values)
        self.collection = store.db[self.collection_name]

    @classmethod
    def get_collection(klass):
        return store.db[klass.collection_name]

    @classmethod
    def find(klass, *args, **kwargs):
        objs = klass.get_collection().find(kwargs)

        for obj in objs:
            yield klass(obj)

    @classmethod
    def get(klass, *args, **kwargs):
        obj = klass.get_collection().find_one(kwargs)

        if obj:
            obj = klass(obj)

        return obj

    def delete(self):
        self.collection.remove(self["_id"])
        del self['_id']

    def save(self):
        if "_id" in self:
            self.collection.replace_one({"_id": self['_id']}, dict(self))
        else:
            self['_id'] = self.collection.insert_one(dict(self)).inserted_id

    def refresh(self):
        new = self.collection.find_one({'_id': self['_id']})
        self.update(new)

    def update_value(self, names, value):
        mongo_field = self._mongo_field(names)

        if isinstance(names, collections.Iterable) and not isinstance(names, basestring):
            last = names.pop()
            self._local_field(names)[last] = value
        else:
            self[names] = value

        return self._update({'$set': {mongo_field: value}})

    def append_to(self, names, value):
        self._local_field(names).append(value)
        return self._update({'$addToSet': {self._mongo_field(names): value}})

    def remove_from(self, names, value):
        local_array = self._local_field(names)

        if value in local_array:
            local_array.remove(value)

        return self._update({'$pull': {self._mongo_field(names): value}})

    def _local_field(self, names):
        local_field = self

        for name in iterify(names):
            if name not in local_field:
                local_field[name] = {}

            local_field = local_field[name]

        return local_field

    def _mongo_field(self, names):
        if isinstance(names, collections.Iterable) and not isinstance(names, basestring):
            return '.'.join(names)
        else:
            return names

    def _update(self, operation, conditions={}):
        query = {'_id': self['_id']}
        query.update(conditions)
        result = self.collection.update_one(query, operation)

        return result.modified_count == 1
