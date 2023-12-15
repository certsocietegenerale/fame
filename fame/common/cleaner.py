from fame.core.config import Config
from fame.core.file import File
from fame.core.analysis import Analysis
from fame.core.user import User
from fame.core.module import ModuleInfo

from datetime import datetime, timedelta


def ignore_file(f, config):
    if f["type"] in config.types_to_exclude:
        return True
    if f["comments"] and config.keep_when_comment:
        return True
    if f["probable_names"] and config.keep_when_probable_name:
        return True
    return False


def get_old_analyses():
    config = Config.get(name="remove_old_data").get_values()
    old_analyses_dict = {}

    if not config or not config.time or config.time <= 0:
        return set(), set()

    since = datetime.now() - timedelta(days=config.time)

    old_analyses = set()
    old_files = set()

    for analysis in Analysis.find({"date": {"$lte": since}}):
        if ignore_file(analysis._file, config):
            continue
        old_analyses.add(analysis)

        # if all the file's analyses are older than the threshold: remove the associated file
        if all(
            [Analysis.get(_id=a)["date"] < since for a in analysis._file["analysis"]]
        ):
            old_files.add(analysis._file)

    for f in File.find({"analysis": []}):
        if ignore_file(f, config):
            continue

        # if the file has parent analyses: keep extracted files if any analysis doesn't meet the threshold
        if any([Analysis.get(_id=a)["date"] > since for a in f["parent_analyses"]]):
            continue

        old_files.add(f)

    return old_analyses, old_files


def get_old_disabled_users():
    config = Config.get(name="remove_old_data").get_values()
    if not config or not config.time or config.time <= 0:
        return set()

    since = datetime.now() - timedelta(days=config.time)

    old_users = set()

    for user in User.find(
        {
            "$or": [
                {"last_activity": {"$lte": since.timestamp()}},
                {"last_activity": {"$exists": False}},
            ]
        },
        enabled=False,
    ):
        old_users.add(user)

    return old_users
