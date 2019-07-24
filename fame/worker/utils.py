import requests

from urlparse import urljoin

from fame.common.config import fame_config


def send_file_to_remote(file, url):
    if isinstance(file, basestring):
        file = open(file, 'rb')

    url = urljoin(fame_config.remote, url)
    response = requests.post(url, files={'file': file},
                             headers={'X-API-KEY': fame_config.api_key})
    response.raise_for_status()

    file.close()

    return response
