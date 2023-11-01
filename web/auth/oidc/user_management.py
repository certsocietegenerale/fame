import os
import requests
from flask_login import login_user
from datetime import datetime
from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse
from jsonpath_ng.exceptions import JSONPathError

from fame.core.user import User
from web.views.helpers import user_if_enabled
from fame.common.config import fame_config
from fame.common.exceptions import MissingConfiguration
from .config import ROLE_MAPPING, USER_CLAIM_MAPPING, API_CLAIM_MAPPING


class ClaimMappingError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


def check_oidc_settings_present():
    def _check(name):
        if name not in fame_config:
            print((name + " not present in config"))
            return False
        return True

    settings = {
        "oidc_authorize_endpoint",  # https://opURL/oauth2/authorize
        "oidc_token_endpoint",  # https://opURL/oauth2/access_token
        "oidc_userinfo_endpoint",  # https://opURL/oauth2/userinfo
        "oidc_tokeninfo_endpoint",  # https://opURL/oauth2/tokeninfo
        "oidc_requested_scopes",  # openid profile Scope1 Scope2
        "oidc_client_id",  # 11111111-1111-1111-1111-111111111111
        "oidc_client_secret",  # ARandomClientSecret
    }

    if not all([_check(s) for s in settings]):
        raise MissingConfiguration(
            f"Missing OIDC configuration in the config file. Please check if the following settings are all configured: %s"
            % ",".join(settings)
        )


def auth_token(user):
    return os.urandom(128).hex()


def authenticate_user(oidc_token):
    userinfo = requests.get(
        fame_config.oidc_userinfo_endpoint,
        headers={"Authorization": "Bearer " + oidc_token},
    ).json()

    claim = {}
    for elem in ["email", "name", "role"]:
        try:
            claim[elem] = parse(USER_CLAIM_MAPPING[elem]).find(userinfo)[0].value
        except (ValueError, IndexError):
            if elem == "role":
                raise ClaimMappingError(f"No role found for '%s'" % userinfo["sub"])
            else:
                raise ClaimMappingError(
                    f"Unable to find '%s' in claims of '%s'. If you are a FAME administrator, check the claim path and user info."
                    % (elem, userinfo["sub"])
                )
        except JSONPathError as e:
            raise ClaimMappingError(
                f"JSON path of claim '%s' is invalid: '%s'. If you are a FAME administrator, please check the claim path in FAME config files."
                % (elem, e.args[0])
            )
    role = None
    for granted_scope in claim["role"]:
        if not role and granted_scope in ROLE_MAPPING:
            role = ROLE_MAPPING[granted_scope]

    if not role:
        raise ClaimMappingError(
            f"User was given role '%s' but this role is not defined in FAME roles mapping. If you ae a FAME administrator, please check the role mapping in config files."
            % claim["role"]
        )

    user = get_or_create_user(claim["email"], claim["name"], role)
    if user:
        user.update_value("last_activity", datetime.now().timestamp())
        user.update_value("auth_token", auth_token(user))
        login_user(user)
    return user


def authenticate_api(tokeninfo):
    claim = {}
    for elem in ["email", "name", "role"]:
        try:
            claim[elem] = parse(API_CLAIM_MAPPING[elem]).find(tokeninfo)[0].value
        except (ValueError, IndexError, JSONPathError):
            return None

    role = None
    for granted_scope in claim["role"]:
        if not role and granted_scope in ROLE_MAPPING:
            role = ROLE_MAPPING[granted_scope]

    if not role:
        return None

    user = get_or_create_user(claim["email"], claim["name"], role)
    return user


def get_or_create_user(mail, name, role):
    user = User.get(email=mail)

    if user:
        return user_if_enabled(user)
    else:

        user = User(
            {
                "email": mail,
                "name": name,
                "groups": role.get("groups", []),
                "default_sharing": role.get("default_sharing", []),
                "permissions": role.get("permissions", []),
                "enabled": True,
            }
        )
        user.save()
        user.generate_avatar()

    return user
