from celery import Celery

celery = Celery('fame.core.celeryctl')
celery.config_from_object('celeryconfig')
