import os
from itsdangerous import TimestampSigner
from flask_login import login_user
from werkzeug.security import check_password_hash, generate_password_hash

from fame.core.user import User
from fame.common.config import fame_config
from web.views.helpers import user_if_enabled


def auth_token(user):
    return os.urandom(128).hex()


def password_reset_token(user):
    signer = TimestampSigner(fame_config.secret_key)

    return signer.sign(str(user['_id']))


def validate_password_reset_token(token):
    signer = TimestampSigner(fame_config.secret_key)

    return signer.unsign(token, max_age=86400)


def create_user(name, email, groups, default_sharing, permissions, password=None):
    user = User.get(email=email.lower())

    if user:
        print("/!\ User with this email address already exists.")
    else:
        user = User({
            'name': name,
            'email': email.lower(),
            'groups': groups,
            'default_sharing': default_sharing,
            'permissions': permissions,
            'enabled': True
        })
        if password:
            user['pwd_hash'] = generate_password_hash(password)
        user.save()
        print("[+] User created.")

        user.generate_avatar()
        print("[+] Downloaded avatar.")

    return user


def authenticate(email, password):
    user = User.get(email=email.lower())

    if user_if_enabled(user):
        if 'pwd_hash' in user:
            if check_password_hash(user['pwd_hash'], password):
                if 'auth_token' not in user:
                    user.update_value('auth_token', auth_token(user))

                login_user(user)
                return user

    return None


def change_password(user, password):
    user.update_value('pwd_hash', generate_password_hash(password))
    user.update_value('auth_token', auth_token(user))
