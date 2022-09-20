#! /usr/bin/env python

import os
import sys

sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
)

from fame.core import fame_init  # noqa: E402
from web.auth.user_password.user_management import (
    create_user as do_create_user,
)  # noqa: E402
from utils import user_input, get_new_password  # noqa: E402


def create_user(admin=False, password=True):
    full_name = user_input("Full Name")
    email = user_input("Email Address")
    groups = user_input("Groups (comma-separated)", "cert").split(",")

    if admin:
        default_sharing = groups
        groups.append("*")
        permissions = ["*"]
    else:
        default_sharing = user_input("Default Sharing Groups (comma-separated)").split(
            ","
        )
        permissions = user_input("Permissions (comma-separated)").split(",")

    if password:
        password = get_new_password()
    else:
        password = None

    do_create_user(full_name, email, groups, default_sharing, permissions, password)


if __name__ == "__main__":
    fame_init()
    create_user()
