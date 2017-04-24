#
# Adds an extra configuration parameter to the VirusTotal settings in 
# the Mongo database.  This setting allows an http proxy to be used.
#

import os
import sys

sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from fame.core.config import Config

vt = Config.get(name='virustotal')
if vt and vt.has_key('config'):
    vt['config'].append({'type': 'str', 'default' : '', 'name':'http_proxy', 'value': None, 'description': 'Optional: HTTP Proxy Server (http://<host>:<port>)'})
vt.save()

