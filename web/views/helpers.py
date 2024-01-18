import urllib.parse
from bson import ObjectId
from flask import make_response, abort, request
from flask_login import current_user
from werkzeug.exceptions import Forbidden
from functools import wraps
from os.path import basename, isfile
from datetime import timedelta, datetime

from fame.core.store import store
from fame.core.config import Config
from fame.common.utils import is_iterable
from fame.common.config import fame_config


def remove_field(instance, field):
    try:
        del instance[field]
    except (KeyError, TypeError):
        pass


def remove_fields(instances, fields):
    if isinstance(instances, dict):
        for field in fields:
            remove_field(instances, field)
    elif is_iterable(instances):
        for instance in instances:
            for field in fields:
                remove_field(instance, field)

    return instances


def clean_objects(instances, filters):
    for permission in filters:
        if permission != "":
            if not current_user.has_permission(permission):
                instances = remove_fields(instances, filters[permission])
        else:
            instances = remove_fields(instances, filters[permission])

    return instances


def clean_analyses(analyses):
    analyses = clean_objects(analyses, {'see_logs': ['logs']})

    return analyses


def enrich_comments(obj):
    if 'comments' in obj and isinstance(obj['comments'], list):
        for comment in obj['comments']:
            if 'analyst' in comment:
                analyst = store.users.find_one({'_id': comment['analyst']})
                comment['analyst'] = clean_users(analyst)

    return obj

def enrich_exists_on_fs(f):
    if f['type'] == 'url' or f['type'] == 'hash':
        f['exists_on_disk'] = True
    else:
        f['exists_on_disk'] = isfile(f['filepath'])
    return f


def clean_files(files):
    files = clean_objects(files, {'': ['filepath']})

    return files


def clean_users(users):
    users = clean_objects(users, {
        '': ['auth_token', 'pwd_hash'],
        'manage_users': ['api_key', 'default_sharing', 'groups', 'permissions']
    })

    return users


def clean_modules(modules):
    modules = clean_objects(modules, {'': ['diffs']})

    return modules


def clean_repositories(repositories):
    repositories = clean_objects(repositories, {'': ['ssh_cmd']})

    return repositories


def user_has_groups_and_sharing(user):
    if len(user['groups']) > 0 and len(user['default_sharing']) > 0:
        return True
    return False


def user_if_enabled(user):
    if user and user['enabled']:
        return user

    return None


def convert_to_seconds(s):
    units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}
    count = int(s[:-1])
    unit = units[s[-1]]
    td = timedelta(**{unit: count})
    return td.seconds + 60 * 60 * 24 * td.days


def disconnect_if_inactive(user):
    if not user or 'last_activity' not in user or fame_config.max_inactivity_time is None:
        return user

    ts = datetime.now().timestamp()
    if user['last_activity'] + convert_to_seconds(fame_config.max_inactivity_time) > ts:
        user.update_value('last_activity', ts)
        return user
    return None


def file_download(filepath):
    if not isfile(filepath):
        abort(404)
    else:
        with open(filepath, 'rb') as fd:
            response = make_response(fd.read())

        response.headers["Content-Disposition"] = "attachment; filename={0}".format(basename(filepath))
        response.headers["Content-Type"] = "application/binary"

        return response


def get_or_404(objectmanager, *args, **kwargs):
    if '_id' in kwargs:
        kwargs['_id'] = ObjectId(kwargs['_id'])

    result = objectmanager.find_one(kwargs)
    if result:
        return result
    else:
        abort(404)


def requires_permission(permission):

    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            if current_user.has_permission(permission):
                return func(*args, **kwargs)
            else:
                abort(403)

        return inner
    return wrapper


def different_origin(referer, target):
    p1, p2 = urllib.parse.urlparse(referer), urllib.parse.urlparse(target)
    origin1 = p1.scheme, p1.hostname, p1.port
    origin2 = p2.scheme, p2.hostname, p2.port

    return origin1 != origin2


def csrf_protect():
    if request.method not in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
        referer = request.headers.get('Referer')

        if referer is None or different_origin(referer, get_fame_url):
            raise Forbidden(description="Referer check failed.")


def prevent_csrf(func):
    @wraps(func)
    def inner(*args, **kwargs):
        csrf_protect()
        return func(*args, **kwargs)

    return inner


def comments_enabled():
    # Determine if comments are enabled
    config = Config.get(name="comments")
    comments_enabled = False

    if config:
        comments_enabled = config.get_values()['enable']

    return comments_enabled


def get_fame_url(default=False):
    if not ' ' in fame_config.fame_url.strip():
        return fame_config.fame_url.strip()

    possible_urls = fame_config.fame_url.strip().split(' ')
    if default or not request:
        return possible_urls[0].strip()

    for possible_url in possible_urls:
        if possible_url.strip() and request.url_root[:-1] == possible_url.strip():
            return possible_url.strip()

    return possible_urls[0].strip()


class BeforeAppFirstRequest:
    funcs = []

    def register(self, func):
        self.funcs.append(func)

    def execute(self, app):
        while self.funcs:
            func = self.funcs.pop()
            func(app)


before_first_request = BeforeAppFirstRequest()
