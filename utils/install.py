import os
import sys
import errno
from urllib import quote_plus
from urlparse import urljoin
from subprocess import call

try:
    from pip._internal import main as pipmain
except ImportError:
    from pip import main as pipmain


sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from utils import user_input, error
from fame.common.constants import FAME_ROOT
from fame.common.output import RedirectedOutput


class Templates:
    def __init__(self):
        from jinja2 import Environment, FileSystemLoader

        self.env = Environment(
            loader=FileSystemLoader(os.path.join(FAME_ROOT, 'utils', 'templates'))
        )

    def save_to(self, filepath, template, context):
        template = self.env.get_template(template)

        with open(filepath, 'w') as f:
            f.write(template.render(context))


def create_conf_directory():
    try:
        os.makedirs(os.path.join(FAME_ROOT, 'conf'))
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise


def test_mongodb_connection(db):
    from pymongo.collection import Collection

    try:
        test_collection = Collection(db, "auth_check", create=True)
        test_collection.drop()
        return True
    except:
        return False


def define_mongo_connection(context):
    from pymongo import MongoClient

    context['mongo_host'] = user_input("MongoDB host", "localhost")
    context['mongo_port'] = int(user_input("MongoDB port", "27017"))
    context['mongo_db'] = user_input("MongoDB database", "fame")

    try:
        mongo = MongoClient(context['mongo_host'], context['mongo_port'], serverSelectionTimeoutMS=10000)
        mongo.server_info()
        db = mongo[context['mongo_db']]
    except Exception, e:
        print e
        error("Could not connect to MongoDB.")

    context['mongo_user'] = ''
    context['mongo_password'] = ''
    if not test_mongodb_connection(db):
        context['mongo_user'] = user_input("MongoDB username")
        context['mongo_password'] = user_input("MongoDB password")
        try:
            db.authenticate(context['mongo_user'], quote_plus(context['mongo_password']))
        except:
            error("Could not connect to MongoDB (invalid credentials).")

        if not test_mongodb_connection(db):
            error("MongDB user has insufficient privileges.")


def define_installation_type(context):
    print "\nChoose your installation type:\n"
    print " - 1: Web server + local worker"
    print " - 2: Remote worker\n"

    itype = user_input("Installation type", "1", ["1", "2"])
    if itype == "1":
        context['installation_type'] = 'local'
    else:
        context['installation_type'] = 'remote'


def generate_ssh_key():
    key_path = os.path.join(FAME_ROOT, 'conf', 'id_rsa')
    if os.path.exists(key_path):
        print "[+] SSH key already exists."
    else:
        print "[+] Generating SSH key ..."
        try:
            call(['ssh-keygen', '-q', '-t', 'rsa', '-b', '4096', '-C', 'FAME deploy key', '-f', key_path, '-N', ''])
        except Exception:
            error("Could not generate SSH key (missing 'ssh-keygen' ?)", exit=False)


def create_admin_user():
    from fame.core.store import store
    from utils.create_user import create_user

    if store.users.count():
        print "[+] There are already users in the database."
    else:
        print "[+] Creating first user (as administrator) ..."
        create_user(admin=True)


def add_community_repository():
    from fame.core.repository import Repository

    repo = Repository.get(name="community")

    if repo:
        print "[+] Community repository already installed."
    else:
        print "[+] Installing community repository ..."
        repo = Repository({
            'name': 'community',
            'address': 'https://github.com/certsocietegenerale/fame_modules.git',
            'private': False,
            'status': 'cloning'
        })
        repo.save()
        repo.do_clone()


def perform_local_installation(context):
    templates = Templates()

    context['fame_url'] = user_input("FAME's URL for users (e.g. https://fame.yourdomain/)")
    print "[+] Creating configuration file ..."
    context['secret_key'] = os.urandom(64).encode('hex')
    templates.save_to(os.path.join(FAME_ROOT, 'conf', 'fame.conf'), 'local_fame.conf', context)

    generate_ssh_key()

    from fame.core import fame_init
    fame_init()
    print "[+] Creating initial data ..."
    from utils.initial_data import create_initial_data
    create_initial_data()

    create_admin_user()
    add_community_repository()


def create_user_for_worker(context):
    from fame.core.user import User
    from web.auth.user_password.user_management import create_user

    worker_user = User.get(email="worker@fame")

    if worker_user:
        print "[+] User for worker already created."
    else:
        print "[+] Creating user for worker ..."
        worker_user = create_user("FAME Worker", "worker@fame", ["*"], ["*"], ["worker"])

    context['api_key'] = worker_user['api_key']


def get_fame_url(context):
    import requests

    context['fame_url'] = user_input("FAME's URL for worker")

    url = urljoin(context['fame_url'], '/modules/download')
    try:
        response = requests.get(url, stream=True, headers={'X-API-KEY': context['api_key']})
        response.raise_for_status()
    except Exception, e:
        print e
        error("Could not connect to FAME.")


def perform_remote_installation(context):
    templates = Templates()

    # Create a temporary configuration file
    context['api_key'] = None
    context['fame_url'] = None
    templates.save_to(os.path.join(FAME_ROOT, 'conf', 'fame.conf'), 'remote_fame.conf', context)

    from fame.core import fame_init
    fame_init()
    create_user_for_worker(context)
    get_fame_url(context)

    # Create definitive configuration file (with api key and URL)
    templates.save_to(os.path.join(FAME_ROOT, 'conf', 'fame.conf'), 'remote_fame.conf', context)


def install_requirements():
    print "[+] Installing requirements ..."

    output = RedirectedOutput()
    rcode = pipmain(['install', '-r', os.path.join(FAME_ROOT, 'requirements.txt')])
    output = output.restore()

    if rcode:
        print output
        error("Could not install requirements.")


def main():
    context = {}

    install_requirements()

    define_mongo_connection(context)

    create_conf_directory()
    define_installation_type(context)
    if context['installation_type'] == 'local':
        perform_local_installation(context)
    else:
        perform_remote_installation(context)


if __name__ == '__main__':
    main()
