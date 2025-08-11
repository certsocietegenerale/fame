import os
import requests
import collections.abc
from time import sleep
from uuid import uuid4
from urllib.parse import urljoin
from datetime import datetime
from shutil import copyfileobj
from werkzeug.utils import secure_filename

from fame.common.config import fame_config


def is_iterable(element):
    return isinstance(element, collections.abc.Iterable) and not isinstance(element, str)


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


def send_file_to_remote(file, url, filename='', via=None):
    if isinstance(file, str):
        file = open(file, 'rb')

    if filename:
        file = (filename, file)

    url = urljoin(fame_config.remote, url)
    response = requests.post(url, files={'file': file}, data={'via': via}, headers={'X-API-KEY': fame_config.api_key})
    response.raise_for_status()

    if filename:
        file = file[1]
    file.close()

    return response


def unique_for_key(l, key):
    return list({d[key]: d for d in l}.values())


def tempdir():
    tempdir = os.path.join(fame_config.temp_path, str(uuid4()).replace('-', ''))

    try:
        os.makedirs(tempdir)
    except:
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

def sanitize_filename(filename, alternative_name):
    if not filename or len(filename) > 1024:
        # CVE-2023-46695: avoid using secure_filename() when the name is too long
        sanitized_filename = alternative_name
    else:
        sanitized_filename = secure_filename(str(filename))

    if not sanitized_filename or len(sanitized_filename) > 200:
        sanitized_filename = alternative_name
    sanitized_filename = sanitized_filename.replace('-', '_')
    return sanitized_filename

def delete_from_disk(top):
    fame_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    )
    if not fame_path in top:
        print(
            "WARNING: refusing to delete '{}' because it is outside of '{}'.".format(
                top, fame_path
            )
        )
        return
    for root, dirs, files in os.walk(top, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    if os.path.isdir(top):
        os.rmdir(top)
    elif os.path.isfile(top):
        os.remove(top)

def retry_read(local_path):
    retries = 7 # We might want to include in a different way as a argument to be more flexible
    for attempt in range(retries):
        delay = 2 ** attempt + random.uniform(0, 1)
        try:
            f = open(local_path, 'xb')
            for chunk in response.iter_content(1024):
                f.write(chunk)
            f.close()
        except FileExistsError:
            self.log(f"Attempt {attempt + 1}/{retries} failed. Retrying in {delay:.2f} seconds...")
            time.sleep(delay)
    raise Exception("All read attempts have failed.")
