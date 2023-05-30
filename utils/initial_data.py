import os
import sys
from time import time

sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from fame.core import fame_init
from fame.core.config import Config
from fame.core.internals import Internals


def create_types():
    types = Config.get(name='types')
    if types is None:
        types = Config({
            'name': 'types',
            'description': 'Mappings for file type determination.',
            'config': [
                {
                    'name': 'mappings',
                    'type': 'text',
                    'value': """[types]

application/x-dosexec = executable
application/vnd.openxmlformats-officedocument.wordprocessingml.document = word
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet = excel
application/msword = word
application/vnd.ms-excel = excel
application/vnd.ms-powerpoint = powerpoint
text/html = html
text/rtf = rtf
application/x-coredump = memory_dump
application/pdf = pdf
application/zip = zip
text/x-mail = eml
message/rfc822 = eml
application/CDFV2-unknown = msg
application/java-archive = jar
application/x-7z-compressed = 7z
application/x-rar = rar
application/x-iso9660-image = iso

[details]

MIME entity, ISO-8859 text, with CRLF line terminators = word
MIME entity, ISO-8859 text, with very long lines, with CRLF line terminators = word
Dalvik dex file = dex

[extensions]

exe = executable
scr = executable
doc = word
docx = word
docm = word
xls = excel
xlsx = excel
xslm = excel
ppt = powerpoint
pptx = powerpoint
rtf = rtf
html = html
js = javascript
pdf = pdf
apk = apk
jar = jar
zip = zip
msg = msg
eml = eml
iso = iso
msi = executable
7z = 7z
rar = rar""",
                    'description': "In order to determine the file type, FAME will use the `python-magic` library. It will then try to find a match in 'mappings' for either the extension, the detailed type or the mime type (in this order of priority). If no matching type was found, the mime type will be used."
                }
            ]
        })

        types.save()


def create_internals():
    updates = Internals.get(name='updates')
    if updates is None:
        updates = Internals({
            'name': 'updates',
            'last_update': time()
        })

        updates.save()


def create_comment_configuration():
    comments = Config.get(name='comments')
    if comments is None:
        comments = Config({
            'name': 'comments',
            'description': 'Analysis comments configuration.',
            'config': [
                {
                    'name': 'enable',
                    'description': 'Let users add comments to an analysis.',
                    'type': 'bool',
                    'default': True,
                    'value': True
                },
                {
                    'name': 'minimum_length',
                    'description': 'Define a minimal character count to be enforced when submitting an analysis',
                    'type': 'integer',
                    'default': 0,
                    'value': None
                }
            ]
        })

        comments.save()


def create_extracted_schedule():
    extracted = Config.get(name="extracted")
    if extracted is None:
        extracted = Config({
            "name": "extracted",
            "description": "Define which modules are scheduled by default on extracted files",
            "config": [
                {
                    "name": "modules",
                    "type": "text",
                    "value": """peepdf
document_preview
exiftool
office_macros
virustotal_public
"""
                }
            ]
        })
        extracted.save()

def create_safe_domains():
    safe_domains = Config.get(name='safe_domains')
    if safe_domains is None:
        safe_domains = Config({
            'name': 'safe_domains',
            'description': 'Define (sub)domains which are trusted and should not be analyzed',
            'config': [
                {
                    'name': 'trusted_domains',
                    'description': 'Safe (sub)domains which should not be analyzed. Users will still be able to force analysis but will be warned before doing so. Only enter domains you own or fully trust in this field\n',
                    'type': 'text',
                    'default': """*.mycompany.lan
www.mycompany.com
192.168.0.0/24
""",
                    'value': None
                },
                {
                    'name': 'untrusted_domains',
                    'description': '(sub)domains which should be considered as untrusted despite being part of a trusted (sub)domain',
                    'type': 'text',
                    'default': """*.untrusted-subdomain.mycompany.lan
untrusted-subdomain.www.mycompany.com
192.168.0.88/30
""",
                    'value': None
                }
            ]
        })

        safe_domains.save()

def create_initial_data():
    create_types()
    create_internals()
    create_safe_domains()
    create_comment_configuration()
    create_extracted_schedule()


if __name__ == '__main__':
    fame_init()
    create_initial_data()
    print("[+] Created initial data.")
