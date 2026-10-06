import datetime
import math

from fame.common.config import fame_config
from fame.core.store import store


def _as_limit(value):
    """Normalize a configured limit. Returns None when there is no limit."""
    if value is None or value == "":
        return None

    try:
        value = int(value)
    except (TypeError, ValueError):
        return None

    return value if value >= 0 else None


def stored_user_limit(user):
    """Raw ``max_submissions_per_day`` field, read with ``[]``: ``MongoDict.get`` is a DB-querying classmethod, not ``dict.get``."""
    try:
        return user["max_submissions_per_day"]
    except (KeyError, TypeError):
        return None


def effective_limit(user):
    """``(limit, source)`` tuple, where source is ``"user"``, ``"global"`` or ``None`` when no limit applies."""
    limit = _as_limit(stored_user_limit(user))
    if limit is not None:
        return limit, "user"

    limit = _as_limit(fame_config.max_submissions_per_day)
    if limit is not None:
        return limit, "global"

    return None, None


def _start_of_day():
    return datetime.datetime.combine(datetime.date.today(), datetime.time.min)


def _count_for(user, source):
    """Number of submissions counted against `user` since midnight (the whole instance when the global limit applies)."""
    query = {"submission": True, "date": {"$gte": _start_of_day()}}

    if source != "global":
        query["analyst"] = user["_id"]

    return store.analysis.count_documents(query)


def status(user):
    """Current quota usage, for display purposes."""
    limit, source = effective_limit(user)
    next_reset = _start_of_day() + datetime.timedelta(days=1)
    seconds = (next_reset - datetime.datetime.now()).total_seconds()

    return {
        "count": _count_for(user, source),
        "limit": limit,
        "reset_in_hours": max(1, int(math.ceil(seconds / 3600))),
    }


def check(user):
    """Returns None when `user` can submit, an error message otherwise."""
    limit, source = effective_limit(user)

    if source is None:
        return None

    if _count_for(user, source) >= limit:
        submissions = "submission" if limit == 1 else "submissions"
        return f"You have reached the daily submission limit ({limit} {submissions} per day). Please try again tomorrow."

    return None
