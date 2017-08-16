import urlparse
from bson import ObjectId
from flask import make_response, abort, request
from flask_login import current_user
from werkzeug.exceptions import Forbidden
from functools import wraps
from os.path import basename
from subprocess import call
from fame.common.utils import is_iterable


def remove_field(instance, field):
    try:
        del instance[field]
    except KeyError:
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


def user_if_enabled(user):
    if user and user['enabled']:
        return user

    return None


def file_download(filepath, password='malware'):
    filename = basename(filepath)
    zipfile = '/tmp/{}.zip'.format(filename)
    call(['7z', 'a', '-p{}'.format(password), '-y', zipfile, filepath])
    with open(zipfile, 'rb') as fd:
        response = make_response(fd.read())

    response.headers["Content-Disposition"] = u"attachment; filename='{0}.zip'".format(filename).encode('latin-1', errors='ignore')

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
    p1, p2 = urlparse.urlparse(referer), urlparse.urlparse(target)
    origin1 = p1.scheme, p1.hostname, p1.port
    origin2 = p2.scheme, p2.hostname, p2.port

    return origin1 != origin2


def csrf_protect():
    if request.method not in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
        referer = request.headers.get('Referer')

        if referer is None or different_origin(referer, request.url_root):
            raise Forbidden(description="Referer check failed.")


def prevent_csrf(func):
    @wraps(func)
    def inner(*args, **kwargs):
        csrf_protect()
        return func(*args, **kwargs)

    return inner
