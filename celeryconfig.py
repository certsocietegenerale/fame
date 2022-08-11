from kombu.serialization import register
from bson.json_util import dumps, loads
from celery import signals

from fame.common.config import fame_config
from fame.core import fame_init

register('json_util', dumps, loads, content_type='application/json', content_encoding='utf-8')

MONGO = 'mongodb://{}:{}/{}'.format(fame_config.mongo_host, fame_config.mongo_port, fame_config.mongo_db)
if fame_config.mongo_user and fame_config.mongo_password:
    MONGO = 'mongodb://{}:{}@{}:{}/{}'.format(fame_config.mongo_user, fame_config.mongo_password, fame_config.mongo_host, fame_config.mongo_port, fame_config.mongo_db)

broker_url = MONGO
accept_content = ['json_util']
task_serializer = 'json_util'

imports = ('fame.core.analysis', 'fame.core.repository')


def connect_to_db(**kwargs):
    fame_init()


signals.worker_process_init.connect(connect_to_db)
