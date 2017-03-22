from fame.core.store import store
from fame.core.module_dispatcher import dispatcher


def fame_init():
    store.connect()
    dispatcher.reload()
