import os

FAME_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
MODULES_ROOT = os.path.join(FAME_ROOT, "fame", "modules")
AVATARS_ROOT = os.path.join(FAME_ROOT, "web", "static", "img", "avatars")
VENDOR_ROOT = os.path.join(FAME_ROOT, "vendor")
