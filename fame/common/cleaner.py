from fame.core.config import Config
from fame.core.file import File
from fame.core.analysis import Analysis
from fame.core.user import User
from fame.core.module import ModuleInfo

from datetime import datetime, timedelta


def ignore_file(f, config):
    if 'type' in f and f["type"] in config.types_to_exclude:
        return True
    if 'comments' in f and f["comments"] and config.keep_when_comment:
        return True
    if 'probable_names' in f and f["probable_names"] and config.keep_when_probable_name:
        return True
    return False


def get_old_analyses():
    config = Config.get(name="cleaner").get_values()

    old_analyses = set()
    old_files = set()

    if config and config.time and config.time > 0:
        since = datetime.now() - timedelta(days=config.time)

        for analysis in Analysis.find({"date": {"$lte": since}}):
            if ignore_file(analysis._file, config):
                continue
            old_analyses.add(analysis)

            # if all the file's analyses are older than the threshold: remove the associated file
            if all(
                [
                    Analysis.get(_id=a)["date"] < since
                    for a in analysis._file["analysis"]
                ]
            ):
                old_files.add(analysis._file)

        for f in File.find({"analysis": []}):
            if ignore_file(f, config):
                continue

            # if the file has parent analyses: keep extracted files if any analysis doesn't meet the threshold
            if 'parent_analyses' in f and any([Analysis.get(_id=a) is not None and Analysis.get(_id=a)["date"] > since for a in f["parent_analyses"]]):
                continue

            old_files.add(f)

    return old_analyses, old_files


def get_old_disabled_users():
    since = datetime.now() - timedelta(days=30)

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
