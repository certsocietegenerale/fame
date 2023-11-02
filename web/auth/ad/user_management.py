import os
import ldap3
import json
from flask_login import login_user
from datetime import datetime

from fame.core.user import User
from fame.common.config import fame_config
from web.auth.ad.config import ROLE_MAPPING
from web.views.helpers import user_if_enabled


class LdapSettingsNotPresentException(Exception):
    pass


class LdapGenericError(Exception):
    pass


def _check_ldap_settings_present():
    def _check(name):
        if name not in fame_config:
            print((name + " not present in config"))
            return False
        return True

    return (
        _check("ldap_uri")
        and _check("ldap_user")
        and _check("ldap_password")
        and _check("ldap_filter_dn")
        and _check("ldap_filter_email")
    )


def _ldap_get_con():
    if not _check_ldap_settings_present():
        raise LdapSettingsNotPresentException
    server = ldap3.Server(fame_config.ldap_uri)
    conn = ldap3.Connection(
        server, fame_config.ldap_user, fame_config.ldap_password, raise_exceptions=True
    )
    bind = conn.bind()
    return conn


def _find_user_by_email(con, email):
    con.search(
        fame_config.ldap_filter_dn,
        fame_config.ldap_filter_email.format(email),
        search_scope=ldap3.SUBTREE,
        size_limit=1,
        attributes=["*"],
    )

    ldap_user = None

    if con.entries:
        user = json.loads(con.entries[0].entry_to_json())

        ldap_user = {
            "dn": user["dn"],
            "name": user["attributes"]["displayName"][0],
            "mail": user["attributes"]["mail"][0],
            "enabled": (user["attributes"]["userAccountControl"][0] & 2 == 0),
            "groups": [
                x.lower().split(",")[0].lstrip("cn=")
                for x in user["attributes"]["memberOf"]
            ],
        }
    return ldap_user


def ldap_authenticate(email, password):
    con = _ldap_get_con()

    ldap_user = _find_user_by_email(con, email)

    if ldap_user:
        server = ldap3.Server(fame_config.ldap_uri)
        conn = ldap3.Connection(
            server, ldap_user["dn"], password, raise_exceptions=True
        )
        bind = conn.bind()
        return ldap_user


def auth_token(user):
    return os.urandom(128).hex()


def get_mapping(collection, name):
    result = set()
    for source_group in collection:
        for mapping in ROLE_MAPPING.get(source_group, {}).get(name, []):
            result.update(mapping)
    return list(result)


def create_user(ldap_user):
    groups = get_mapping(ldap_user["groups"], "groups")
    default_sharing = get_mapping(ldap_user["groups"], "default_sharing")
    permissions = get_mapping(ldap_user["groups"], "permissions")

    user = User(
        {
            "name": ldap_user["name"],
            "email": ldap_user["mail"],
            "enabled": ldap_user["enabled"],
            "groups": groups,
            "default_sharing": default_sharing,
            "permissions": permissions,
            "last_activity": datetime.now().timestamp(),
        }
    )
    user.save()
    user.generate_avatar()

    return user


def update_or_create_user(ldap_user):
    user = User.get(email=ldap_user["mail"])

    if user:
        # update groups
        groups = get_mapping(ldap_user["groups"], "groups")
        user.update_value("groups", groups)

        # update default sharings
        default_sharing = get_mapping(ldap_user["groups"], "default_sharing")
        user.update_value("default_sharing", default_sharing)

        # update permissions
        permissions = get_mapping(ldap_user["groups"], "permissions")
        user.update_value("permissions", permissions)

        # enable/disable user
        user.update_value("enabled", ldap_user["enabled"])

        user.update_value("last_activity", datetime.now().timestamp())

        return user_if_enabled(user)

    return create_user(ldap_user)


def authenticate(email, password):
    ldap_user = ldap_authenticate(email, password)

    if not ldap_user:
        # user not found in LDAP, update local user object accordingly (if existent)
        user = User.get(email=email)
        if user and user["enabled"]:
            user.update_value("enabled", False)
            raise LdapGenericError(
                "User {} does not exists in LDAP anymore".format(email)
            )
        return None

    user = update_or_create_user(ldap_user)

    if user:
        user.update_value("last_activity", datetime.now().timestamp())
        user.update_value("auth_token", auth_token(user))
        login_user(user)
    return user
