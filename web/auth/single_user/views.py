from flask_login import login_user
from flask import Blueprint, request, redirect
from fame.common.config import fame_config
from urllib.parse import urljoin

from fame.core.user import User
from web.views.helpers import prevent_csrf


auth = Blueprint('auth', __name__, template_folder='templates')


def get_or_create_user():
    user = User.get(email="admin@fame")

    if not user:
        user = User({
            'name': "admin",
            'email': "admin@fame",
            'groups': ['admin', '*'],
            'default_sharing': ['admin'],
            'permissions': ['*'],
            'enabled': True
        })
        user.save()
        user.generate_avatar()

    return user


@auth.route('/login', methods=['GET', 'POST'])
@prevent_csrf
def login():
    redir = request.args.get('next', '/')

    if "/login" in redir:
        redir = '/'

    user = get_or_create_user()
    user.update_value('last_activity', datetime.now().timestamp())
    login_user(user)

    return redirect(urljoin(fame_config.fame_url, redir))


@auth.route('/logout')
def logout():
    redir = '/'
    return redirect(urljoin(fame_config.fame_url, redir))
