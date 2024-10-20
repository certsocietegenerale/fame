import os
import requests
import json
from flask_login import login_user
from datetime import datetime
from josepy.jwk import JWK
from josepy.jws import JWS
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
            print(name + " not present in config")
            return False
        return True

    settings = {
        "oidc_authorize_endpoint",
        "oidc_token_endpoint",
        "oidc_userinfo_endpoint",
        "oidc_jwk_uri_endpoint",
        "oidc_requested_scopes",
        "oidc_client_id",
        "oidc_client_secret",
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
            headers={"Authorization": "Bearer " + oidc_token["access_token"]},
        ).json()
    except requests.exceptions.RequestException as e:
        return ClaimMappingError(
            f"Unable to contact the OIDC server: %s. If you are a FAME administrator, please check the value of oidc_userinfo_endpoint."
            % e.args[0]
        )

    access_token = verify_jwt(oidc_token["access_token"])
    if access_token:
        userinfo.update(access_token)

    try:
        id_token = verify_jwt(oidc_token["id_token"])
        if id_token:
            userinfo.update(id_token)
    except KeyError:
        pass

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
            % (userinfo["sub"], ",".join(claim["role"]))
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


def verify_jwt(token):
    try:
        jwks = requests.get(fame_config.oidc_jwk_uri_endpoint).json()
    except requests.exceptions.RequestException as e:
        print(
            "WARNING: Unable to contact the OIDC server: %s. Please check the value of oidc_jwk_uri_endpoint"
            % e.args[0]
        )
        return False

    try:
        token = JWS.from_compact(token.encode())
        alg = json.loads(token.signature.protected)["alg"]
        jwt_content = json.loads(token.payload.decode("utf-8"))
    except (UnicodeDecodeError, KeyError, json.decoder.JSONDecodeError):
        # token is not a valid JWT
        return False

    for jwk in jwks["keys"]:
        if jwk["alg"] == alg:
            if token.verify(JWK.from_json(jwk)):
                return jwt_content

    # token verification failed
    return False
