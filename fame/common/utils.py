import os
import requests
import collections
from time import sleep
from uuid import uuid4
from urllib.parse import urljoin
from datetime import datetime
from shutil import copyfileobj
from werkzeug.utils import secure_filename

from fame.common.config import fame_config


def is_iterable(element):
    return isinstance(element, collections.Iterable) and not isinstance(element, str)


def iterify(element):
    if is_iterable(element):
        return element
    else:
        return (element,)


def u(string):
    try:
        return str(string)
    except UnicodeDecodeError:
        try:
            return str(string, 'latin-1')
        except UnicodeDecodeError:
            return str(string, errors='replace')


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


def ordered_list_value(list_of_values):
    result = []

    for value in list_of_values.split(','):
        value = value.strip()
        result.append(value)

    return result


def send_file_to_remote(file, url):
    if isinstance(file, str):
        file = open(file, 'rb')

    url = urljoin(fame_config.remote, url)
    response = requests.post(url, files={'file': file}, headers={'X-API-KEY': fame_config.api_key})
    response.raise_for_status()

    file.close()

    return response


def unique_for_key(li, key):
    return list({d[key]: d for d in li}.values())


def tempdir():
    tempdir = os.path.join(fame_config.temp_path, str(uuid4()).replace('-', ''))

    try:
        os.makedirs(tempdir)
    except Exception:
        pass

    return tempdir


def save_response(response, filepath):
    tmp = tempdir()
    filename = secure_filename(os.path.basename(filepath))
    filepath = os.path.join(tmp, filename)

    with open(filepath, 'wb') as out:
        copyfileobj(response.raw, out)

    return filepath


def with_timeout(func, timeout, step):
    started_at = datetime.now()

    while started_at + timeout > datetime.now():
        result = func()

        if result:
            return result

        sleep(step)

    return None
