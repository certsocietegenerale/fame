import os
import sys
from git import Repo

sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from utils import error
from fame.common.constants import FAME_ROOT
from fame.common.pip import pip_install


def update_repository():
    print("[+] Updating repository ...")
    try:
        repo = Repo(FAME_ROOT)
        repo.remotes.origin.pull()
    except Exception as e:
        error("Could not update repository: {}".format(e))


def update_requirements():
    print("[+] Updating requirements ...")

    rcode, output = pip_install('-r', os.path.join(FAME_ROOT, 'requirements.txt'))

    # In case pip failed
    if rcode:
        error("Could not update requirements: {}".format(output))


def end_message():
    print("\n[+] Successfully updated FAME. Restart webserver and workers for changes to be effective.")


def main():
    update_repository()
    update_requirements()

    # Make sure basic configuration values are present
    from utils.initial_data import create_initial_data
    create_initial_data()

    end_message()


if __name__ == '__main__':
    main()
