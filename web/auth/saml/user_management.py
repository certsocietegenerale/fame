from flask_login import login_user
from datetime import datetime

from fame.core.user import User
from web.views.helpers import user_if_enabled
from .config import ROLE_MAPPING, ROLE_KEY


def authenticate(session):
    saml_user_data = session["samlUserdata"]
    saml_name_id = session["samlNameId"]
    user = get_or_create_user(saml_name_id, saml_user_data)

    if user:
        user.update_value("last_activity", datetime.now().timestamp())
        login_user(user)

    return user


def get_or_create_user(saml_name_id, saml_user_data):
    user = User.get(saml_name_id=saml_name_id)

    if user:
        return user_if_enabled(user)

    return create_user(saml_name_id, saml_user_data)


def create_user(saml_name_id, saml_user_data):

    role = saml_user_data[ROLE_KEY][0]

    user = User(
        {
            "saml_name_id": saml_name_id,
            "name": saml_name_id,
            "groups": ROLE_MAPPING[role]["groups"],
            "default_sharing": ROLE_MAPPING[role]["default_sharing"],
            "permissions": ROLE_MAPPING[role]["permissions"],
            "enabled": True,
        }
    )
    user.save()
    user.generate_avatar()

    return user
