import os
import requests
import collections
from uuid import uuid4
from urlparse import urljoin

from fame.common.config import fame_config


def is_iterable(element):
    return isinstance(element, collections.Iterable) and not isinstance(element, basestring)


def iterify(element):
    if is_iterable(element):
        return element
    else:
        return (element,)


def u(string):
    try:
        return unicode(string)
    except UnicodeDecodeError:
        try:
            return unicode(string, 'latin-1')
        except UnicodeDecodeError:
            return unicode(string, errors='replace')


def get_class(module, klass):
    try:
        m = __import__(module)
        for part in module.split('.')[1:]:
            m = getattr(m, part)

        return getattr(m, klass)
    except (ImportError, AttributeError):
        return None


def list_value(list_of_values):
    result = set()

    for value in list_of_values.split(','):
        value = value.strip()
        if value != "":
            result.add(value)

    return list(result)


def send_file_to_remote(file, url):
    if isinstance(file, basestring):
        file = open(file, 'rb')

    url = urljoin(fame_config.remote, url)
    response = requests.post(url, files={'file': file}, headers={'X-API-KEY': fame_config.api_key})
    response.raise_for_status()

    file.close()

    return response


def unique_for_key(l, key):
    return {d[key]: d for d in l}.values()


def tempdir():
    tempdir = os.path.join(fame_config.temp_path, str(uuid4()).replace('-', ''))

    try:
        os.makedirs(tempdir)
    except:
        pass

    return tempdir
