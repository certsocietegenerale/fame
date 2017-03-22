from bson import ObjectId
from difflib import ndiff
from flask import request, abort
from flask_login import current_user
from flask_classy import FlaskView

from fame.core.store import store
from web.views.negotiation import render
from web.views.mixins import UIView


ACTION_NEW = 'new'
ACTION_UPDATE = 'update'
ACTION_REMOVED = 'removed'


def clean_record(record):
    record['target'] = record['_id']['target']
    record['monitor'] = record['_id']['monitor']
    record['botnet'] = record['_id']['botnet']
    record['type'] = record['_id']['type']
    del record['_id']


def targets_aggregation():
    return store.config_blocks.aggregate([
            { '$sort': { 'updated': 1 }},
            { '$group': {
                '_id': { 'target': '$target', 'monitor': '$monitor', 'botnet': '$botnet', 'type': '$type' },
                'count': { '$sum': 1 },
                'last_action': { '$last': '$action' }
            }}
        ])


def get_monitor(monitors, record):
    if record['monitor'] not in monitors:
        monitors[record['monitor']] = {'count': 0, 'botnets': set(), 'active_botnets': set(), 'targets': {}}

    return monitors[record['monitor']]


def get_target(monitor, record):
    if record['target'] not in monitor['targets']:
        monitor['targets'][record['target']] = {'count': 0, 'botnets': set(), 'active_botnets': set()}

    return monitor['targets'][record['target']]


def increment(dicts, key, value=1):
    for d in dicts:
        d[key] += value


def add(dicts, key, value):
    for d in dicts:
        d[key].add(value)


def build_query(fields):
    query = {}

    for field in fields:
        if request.args.get(field):
            query[field] = request.args.get(field)

    return query


class ConfigsView(FlaskView, UIView):
    def before_request(self, *args, **kwargs):
        redir = UIView.before_request(self, *args, **kwargs)
        if redir:
            return redir

        if not current_user.has_permission('configs'):
            abort(404)

    def index(self):
        """Get the index of malware configurations.

        .. :quickref: Malware Configurations; Get the index

        Requires the `config` permission.

        The response is a dict with the following format::

            {
                "MONITOR1": {
                    "active_botnets": [
                        "FAMILY:BOTNETID"
                    ],
                    "botnets": [
                        "FAMILY:BOTNETID"
                    ],
                    "count": 1,
                    "targets": {
                        "TARGET1": {
                            "active_botnets": [
                                "FAMILY:BOTNETID"
                            ],
                            "botnets": [
                                "FAMILY:BOTNETID"
                            ],
                            "count": 1
                        },
                        "TARGET2": {
                            ...
                        }
                    }
                },
                "MONITOR2": {
                    ...
                }
            }
        """
        monitors = {}

        for record in targets_aggregation():
            clean_record(record)
            monitor = get_monitor(monitors, record)
            target = get_target(monitor, record)

            increment([monitor, target], 'count', record['count'])
            add([monitor, target], 'botnets', record['botnet'])
            if record['last_action'] != ACTION_REMOVED:
                add([monitor, target], 'active_botnets', record['botnet'])

        return render(monitors, 'configs/index.html')

    def show(self):
        """Get a malware configuration timeline.

        .. :quickref: Malware Configurations; Get a timeline

        Requires the `config` permission.

        You can get the timeline of your choice by conbining several filters.

        :query monitor: (optional) filter by monitor.
        :query target: (optional) filter by target.
        :query botnet: (optional) filter by botnet.
        :query type: (optional) filter by type.

        :>json list botnets: the list of available botnets.
        :>json list monitors: the list of available monitors.
        :>json list targets: the list of available targets.
        :>json list types: the list of available configuration block types.
        :>json list config_blocks: a sorted list of configuration blocks matching
            this query. Each configuration block has the following format::

                {
                    "_id": {
                        "$oid": "CONFIG_BLOCK_ID"
                    },
                    "action": "CONFIG_BLOCK_ACTION", # new, update, removed or added
                    "additional": null,
                    "analyses": [
                        {
                            "$oid": "ANALYSIS_ID"
                        }
                    ],
                    "botnet": "FAMILY:BOTNETID",
                    "content": "CONFIG_BLOCK_CONTENT",
                    "created": {
                        "$date": CREATION_DATE
                    },
                    "monitor": "MATCHING_MONITOR",
                    "target": "TARGET",
                    "type": "CONFIG_BLOCK_TYPE",
                    "updated": {
                        "$date": MODIFICATION_DATE
                    }
                }
        """
        query = build_query(['monitor', 'target', 'botnet', 'type'])

        history = {}
        monitors = set()
        targets = set()
        types = set()
        botnets = set()
        config_blocks = []
        for block in store.config_blocks.find(query).sort('updated'):
            config_blocks.append(block)
            monitors.add(block['monitor'])
            targets.add(block['target'])
            types.add(block['type'])
            botnets.add(block['botnet'])

            label = "{}:{}:{}".format(block['target'], block['type'], block['botnet'])
            if block['action'] == ACTION_UPDATE:
                block['diff'] = ''.join(ndiff(history[label].splitlines(1), block['content'].splitlines(1)))

            if block['action'] != ACTION_REMOVED:
                history[label] = block['content']

        result = {
            'config_blocks': config_blocks,
            'monitors': monitors,
            'targets': targets,
            'types': types,
            'botnets': botnets
        }

        return render(result, 'configs/show.html')

    def delete(self, id):
        store.config_blocks.remove(ObjectId(id))

        return 'ok'
