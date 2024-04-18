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
    try:
        userinfo = requests.get(
            fame_config.oidc_userinfo_endpoint,
            headers={"Authorization": "Bearer " + oidc_token},
        ).json()
    except requests.exceptions.RequestException as e:
        return ClaimMappingError(
            f"Unable to contact the OIDC server: %s. If you are a FAME administrator, please check the value of oidc_userinfo_endpoint."
            % e.args[0]
        )

    claim = {}
    for elem in ["email", "name", "role"]:
        try:
            if elem == "role":
                claim["role"] = []
                for found_role in parse(USER_CLAIM_MAPPING[elem]).find(userinfo):
                    if isinstance(found_role.value, str):
                        claim["role"] += found_role.value.split(" ")
                    elif isinstance(found_role.value, list):
                        claim["role"] += found_role.value
                    else:
                        claim["role"].append(found_role.value)
            else:
                claim[elem] = parse(USER_CLAIM_MAPPING[elem]).find(userinfo)[0].value
        except (ValueError, IndexError):
            if elem == "role":
                # If user has no role: disable it
                user = User.get(email=claim["email"])
                if user:
                    user.update_value("enabled", False)
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

    role = {}
    for granted_scope in claim["role"]:
        if granted_scope in ROLE_MAPPING:
            for elem in ["permissions", "groups", "default_sharing"]:
                if elem in ROLE_MAPPING[granted_scope]:
                    existing_value = role.get(elem, [])
                    role[elem] = list(
                        set(existing_value + ROLE_MAPPING[granted_scope][elem])
                    )

    if not role:
        # If user has no role: disable it
        user = User.get(email=claim["email"])
        if user:
            user.update_value("enabled", False)

        raise ClaimMappingError(
            f"Role(s) found for '%s' (%s) do not allow FAME access."
            % (userinfo["sub"], ','.join(claim["role"]))
        )

    user = update_or_create_user(claim["email"], claim["name"], role)
    if user:
        user.update_value("last_activity", datetime.now().timestamp())
        user.update_value("auth_token", auth_token(user))
        login_user(user)
    return user


def authenticate_api(tokeninfo):
    claim = {}
    for elem in ["email", "name", "role"]:
        try:
            if elem == "role":
                claim["role"] = []
                for found_role in parse(API_CLAIM_MAPPING[elem]).find(tokeninfo):
                    if isinstance(found_role.value, str):
                        claim["role"] += found_role.value.split(" ")
                    elif isinstance(found_role.value, list):
                        claim["role"] += found_role.value
                    else:
                        claim["role"].append(found_role.value)
            else:
                claim[elem] = parse(API_CLAIM_MAPPING[elem]).find(tokeninfo)[0].value
        except (ValueError, IndexError, JSONPathError):
            return None

    role = {}
    for granted_scope in claim["role"]:
        if granted_scope in ROLE_MAPPING:
            for elem in ["permissions", "groups", "default_sharing"]:
                if elem in ROLE_MAPPING[granted_scope]:
                    existing_value = role.get(elem, [])
                    role[elem] = list(
                        set(existing_value + ROLE_MAPPING[granted_scope][elem])
                    )

    if not role:
        return None

    user = update_or_create_user(claim["email"], claim["name"], role)
    return user


def update_or_create_user(mail, name, role):
    user = User.get(email=mail)

    if user:
        user.update_value("name", name)
        user.update_value("enabled", True)

        if role.get("default_sharing"):
            user.update_value("default_sharing", role.get("default_sharing"))
        if role.get("permissions"):
            user.update_value("permissions", role.get("permissions"))
        if role.get("groups"):
            user.update_value("groups", role.get("groups"))

        return user
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
