import os
import sys

sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from fame.core import fame_init
from utils.initial_data import create_initial_data
from utils.install import create_admin_user, create_user_for_worker, add_community_repository


def main():
    fame_init()

    print("[+] Creating initial data ...")
    create_initial_data()

    print("[+] Creating users...")
    create_admin_user()
    create_user_for_worker(dict())

    if os.getenv("FAME_INSTALL_COMMUNITY_REPO", "1") == "1":
        add_community_repository()


if __name__ == "__main__":
    main()
