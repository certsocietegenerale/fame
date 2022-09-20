import os
import sys
import errno
from urllib.parse import quote_plus
from urllib.parse import urljoin
from subprocess import run, PIPE

sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
)

from utils import user_input, error, get_new_password  # noqa: E402
from fame.common.constants import FAME_ROOT  # noqa: E402


class Templates:
    def __init__(self):
        from jinja2 import Environment, FileSystemLoader

        self.env = Environment(
            loader=FileSystemLoader(os.path.join(FAME_ROOT, "utils", "templates"))
        )

    def save_to(self, filepath, template, context):
        template = self.env.get_template(template)

        with open(filepath, "w") as f:
            f.write(template.render(context))


def create_conf_directory():
    try:
        os.makedirs(os.path.join(FAME_ROOT, "conf"))
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def test_mongodb_connection(db):
    from pymongo.collection import Collection

    try:
        test_collection = Collection(db, "auth_check", create=True)
        test_collection.drop()
        return True
    except Exception:
        return False


def define_mongo_connection(context):
    from pymongo import MongoClient

    context["mongo_host"] = os.environ.get("MONGODB_HOST", "localhost")
    context["mongo_port"] = int(os.environ.get("MONGODB_PORT", 27017))
    context["mongo_db"] = os.environ.get("MONGO_INITDB_DATABASE", "fame")
    context["mongo_user"] = os.environ.get("MONGODB_USERNAME", "")
    context["mongo_password"] = os.environ.get("MONGODB_PASSWORD", "")

    if context["interactive"]:
        context["mongo_host"] = user_input("MongoDB host", context["mongo_host"])
        context["mongo_port"] = int(user_input("MongoDB port", context["mongo_port"]))
        context["mongo_db"] = user_input("MongoDB database", context["mongo_db"])
        context["mongo_user"] = user_input("MongoDB username", context["mongo_user"])
        context["mongo_password"] = user_input(
            "MongoDB password", context["mongo_password"]
        )

    try:
        mongo = MongoClient(
            context["mongo_host"], context["mongo_port"], serverSelectionTimeoutMS=10000
        )
        mongo.server_info()
        db = mongo[context["mongo_db"]]
    except Exception as e:
        print(e)
        error("Could not connect to MongoDB.")

    if not test_mongodb_connection(db):
        try:
            db.authenticate(
                context["mongo_user"], quote_plus(context["mongo_password"])
            )
        except Exception:
            error("Could not connect to MongoDB (invalid credentials).")

        if not test_mongodb_connection(db):
            error("MongDB user has insufficient privileges.")


def generate_ssh_key():
    key_path = os.path.join(FAME_ROOT, "conf", "id_rsa")
    if os.path.exists(key_path):
        print("[+] SSH key already exists.")
    else:
        if os.environ.get("FAME_GIT_SSH_KEY", ""):
            print("[+] installing provided SSH key ...")
            key_file = open(key_path, "w+")
            key_file.write(os.environ.get("FAME_GIT_SSH_KEY", "").replace("\\n", "\n"))
            key_file.close()
            os.chmod(key_path, 0o600)

            try:
                pubkey = run(
                    ["ssh-keygen", "-y", "-C", "FAME deploy key", "-f", key_path],
                    stdout=PIPE,
                )
            except Exception:
                error(
                    "Could not generate SSH key (missing 'ssh-keygen' ? Invalid key?)",
                    exit=False,
                )

            if pubkey:
                pubkey_file = open(key_path + ".pub", "w+")
                pubkey_file.write(pubkey.stdout.decode())
                pubkey_file.close()
        else:
            print("[+] Generating SSH key ...")
            try:
                run(
                    [
                        "ssh-keygen",
                        "-q",
                        "-t",
                        "rsa",
                        "-b",
                        "4096",
                        "-C",
                        "FAME deploy key",
                        "-f",
                        key_path,
                        "-N",
                        "",
                    ]
                )
            except Exception:
                error("Could not generate SSH key (missing 'ssh-keygen' ?)", exit=False)


def create_admin_user(context):
    from fame.core.store import store
    from web.auth.user_password.user_management import create_user

    if store.users.count_documents({}):
        print("[+] There are already users in the database.")
    else:
        print("[+] Creating first user (as administrator) ...")
        default_user_email = os.environ.get("DEFAULT_EMAIL", "admin@changeme.fame")
        default_user_password = os.environ.get("DEFAULT_PASSWORD", "")
        if context["interactive"]:
            default_user_email = user_input("User email address:", default_user_email)
            if not default_user_password:
                default_user_password = get_new_password()

        if not default_user_password:
            error(
                "Error: No password given for the default account. Did you set DEFAULT_EMAIL / DEFAULT_PASSWORD ?"
            )

        create_user(
            "Admin",
            default_user_email,
            ["*", "cert"],
            ["cert"],
            ["*"],
            default_user_password,
        )


def add_community_repository():
    from fame.core.repository import Repository

    repo = Repository.get(name="community")

    if repo:
        print("[+] Community repository already installed.")
    else:
        print("[+] Installing community repository ...")
        repo = Repository(
            {
                "name": "community",
                "address": "https://github.com/certsocietegenerale/fame_modules.git",
                "private": False,
                "status": "cloning",
            }
        )
        repo.save()
        repo.do_clone()


def perform_local_installation(context):
    templates = Templates()

    context["fame_url"] = os.environ.get("FAME_URL", "http://localhost")
    if context["interactive"]:
        context["fame_url"] = user_input("FAME's URL for worker", context["fame_url"])
    print("[+] Creating configuration file ...")
    context["secret_key"] = os.urandom(64).hex()
    templates.save_to(
        os.path.join(FAME_ROOT, "conf", "fame.conf"), "local_fame.conf", context
    )

    generate_ssh_key()

    from fame.core import fame_init
    from web.auth.user_password.user_management import create_user

    fame_init()
    print("[+] Creating initial data ...")
    from utils.initial_data import create_initial_data

    create_initial_data()

    create_admin_user(context)
    add_community_repository()


def create_user_for_worker(context):
    from fame.core.user import User
    from web.auth.user_password.user_management import create_user

    worker_user = User.get(email="worker@fame")

    if worker_user:
        print("[+] User for worker already created.")
    else:
        print("[+] Creating user for worker ...")
        worker_user = create_user(
            "FAME Worker", "worker@fame", ["*"], ["*"], ["worker"]
        )

    context["api_key"] = worker_user["api_key"]


def get_fame_url(context):
    import requests

    context["fame_url"] = os.environ.get("FAME_URL", "http://localhost")

    url = urljoin(context["fame_url"], "/modules/download")
    try:
        response = requests.get(
            url, stream=True, headers={"X-API-KEY": context["api_key"]}
        )
        response.raise_for_status()
    except Exception as e:
        print(e)
        error("Could not connect to FAME.")


def perform_remote_installation(context):
    templates = Templates()

    # Create a temporary configuration file
    context["api_key"] = None
    context["fame_url"] = None
    templates.save_to(
        os.path.join(FAME_ROOT, "conf", "fame.conf"), "remote_fame.conf", context
    )

    from fame.core import fame_init

    fame_init()
    create_user_for_worker(context)
    get_fame_url(context)

    # Create definitive configuration file (with api key and URL)
    templates.save_to(
        os.path.join(FAME_ROOT, "conf", "fame.conf"), "remote_fame.conf", context
    )


def main():
    context = {}

    context["interactive"] = True
    if sys.argv and any([arg == "--not-interactive" for arg in sys.argv]):
        print("[+] Performing a non-interactive installation")
        context["interactive"] = False

    define_mongo_connection(context)

    create_conf_directory()

    itype = "1"
    if sys.argv and any([arg == "worker" for arg in sys.argv]):
        itype = "2"

    if context["interactive"]:
        print("\nChoose your installation type:\n")
        print(" - 1: Web server + local worker")
        print(" - 2: Remote worker\n")
        itype = user_input("Installation type", itype, ["1", "2"])

    if itype == "1":
        print("[+] performing local install")
        perform_local_installation(context)
    else:
        print("[+] performing remote install")
        perform_remote_installation(context)


if __name__ == "__main__":
    main()
