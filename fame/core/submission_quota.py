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


def global_limit():
    return _as_limit(fame_config.max_submissions_per_day)


def user_limit(user):
    return _as_limit(user.get("max_submissions_per_day"))


def effective_limit(user):
    """Returns a ``(limit, source)`` tuple.

    ``source`` is ``"user"``, ``"global"`` or ``None`` when no limit applies.
    """
    limit = user_limit(user)
    if limit is not None:
        return limit, "user"

    limit = global_limit()
    if limit is not None:
        return limit, "global"

    return None, None


def _start_of_day():
    return datetime.datetime.combine(datetime.date.today(), datetime.time.min)


def hours_until_reset():
    """Number of hours before the daily counts start over (at least 1)."""
    next_reset = _start_of_day() + datetime.timedelta(days=1)
    seconds = (next_reset - datetime.datetime.now()).total_seconds()

    return max(1, int(math.ceil(seconds / 3600)))


def _count(query):
    query = dict(query, submission=True, date={"$gte": _start_of_day()})

    return store.analysis.count_documents(query)


def user_count(user):
    """Number of analyses submitted by `user` today."""
    return _count({"analyst": user["_id"]})


def global_count():
    """Number of analyses submitted on this instance today."""
    return _count({})


def status(user):
    """Current quota usage, for display purposes."""
    limit, source = effective_limit(user)
    count = global_count() if source == "global" else user_count(user)

    return {
        "count": count,
        "limit": limit,
        "reset_in_hours": hours_until_reset(),
    }


def check(user):
    """Returns None when `user` can submit, an error message otherwise."""
    limit, source = effective_limit(user)

    if source is None:
        return None

    count = global_count() if source == "global" else user_count(user)

    if count >= limit:
        return f"You have reached the daily submission limit ({limit} submissions per day). Please try again tomorrow."

    return None
