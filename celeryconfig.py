from kombu.serialization import register
from bson.json_util import dumps, loads
from celery import signals

from fame.common.config import fame_config
from fame.core import fame_init

register('json_util', dumps, loads, content_type='application/json', content_encoding='utf-8')

MONGO = 'mongodb://{}:{}/{}'.format(fame_config.mongo_host, fame_config.mongo_port, fame_config.mongo_db)
if fame_config.mongo_user and fame_config.mongo_password:
    MONGO = 'mongodb://{}:{}@{}:{}/{}'.format(fame_config.mongo_user, fame_config.mongo_password, fame_config.mongo_host, fame_config.mongo_port, fame_config.mongo_db)

BROKER_URL = MONGO
CELERY_RESULT_BACKEND = MONGO
CELERY_ACCEPT_CONTENT = ['json_util']
CELERY_TASK_SERIALIZER = 'json_util'

CELERY_IMPORTS = ('fame.core.analysis', 'fame.core.repository')


def connect_to_db(**kwargs):
    fame_init()

    from fame.core.user import User
    worker_user = User.get(email="worker@fame")
    if worker_user:
        fame_config.api_key = worker_user['api_key']


if fame_config.is_worker:
    try:
        from celeryconfig_worker import *
    except ImportError:
        pass

signals.worker_process_init.connect(connect_to_db)
