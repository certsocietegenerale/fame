#! /usr/bin/env python

import os
import sys

sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from fame.core import fame_init
from web.auth.user_password.user_management import create_user as do_create_user
from utils import user_input, get_new_password


def create_user(admin=False, password=True):
    full_name = os.getenv("FAME_ADMIN_FULLNAME", "")
    if not full_name:
        full_name = user_input("Full Name")

    email = os.getenv("FAME_ADMIN_EMAIL", "")
    if not email:
        email = user_input("Email Address")

    groups = os.getenv("FAME_ADMIN_GROUPS", "")
    if not groups:
        groups = user_input("Groups (comma-separated)", "cert")
    groups = groups.split(",")

    if admin:
        default_sharing = groups
        groups.append('*')
        permissions = ['*']
    else:
        default_sharing = os.getenv("FAME_ADMIN_DEFAULT_SHARING", "")
        if not default_sharing:
            default_sharing = user_input("Default Sharing Groups (comma-separated)")
        default_sharing = default_sharing.split(",")

        permissions = os.getenv("FAME_ADMIN_PERMISSIONS", "")
        if not permissions:
            permissions = user_input("Permissions (comma-separated)")
        permissions = permissions.split(",")

    if password:
        password = os.getenv("FAME_ADMIN_PASSWORD", "")
        if not password:
            password = get_new_password()
    else:
        password = None

    do_create_user(full_name, email, groups, default_sharing, permissions, password)


if __name__ == '__main__':
    fame_init()
    create_user()
