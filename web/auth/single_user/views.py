from urlparse import urlparse
from flask_login import login_user, make_secure_token
from fame.core.user import User
import os

from flask import Blueprint, request, redirect, session

from web.views.helpers import prevent_csrf



auth = Blueprint('auth', __name__, template_folder='templates')


def create_user():
    from fame.core.store import store
    if not store.users.count():
        user = User({
            'name': "admin",
            'email': "admin@fame",
            'groups': ['admin','*'],
            'default_sharing' : ['admin'],
            'permissions': ['*'],
            'enabled': True
        })
        user.save()
        user.generate_avatar()

    return True


@auth.route('/login', methods=['GET', 'POST'])
@prevent_csrf
def login():
    redir = request.args.get('next', '/')

    if "/login" in redir:
        redir = '/'
    login_user(User.get(email="admin@fame"))


    return redirect(redir)


@auth.route('/logout')
def logout():
    redir = '/'
    return redirect(redir)
