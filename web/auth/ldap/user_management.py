import codecs
import os
import ldap
from itsdangerous import TimestampSigner
from flask_login import login_user, make_secure_token

from fame.core.user import User
from fame.common.config import fame_config
from web.auth.ldap.config import ROLE_MAPPING
from web.views.helpers import user_if_enabled

ldap.set_option(ldap.OPT_X_TLS_NEWCTX, ldap.OPT_X_TLS_DEMAND)


def _ldap_get_con():
    con = ldap.initialize(fame_config.ldap_uri)
    con.protocol_version = ldap.VERSION3
    con.set_option(ldap.OPT_REFERRALS, 0)
    return con


def _find_user_by_email(con, email):
    try:
        con.simple_bind_s(fame_config.ldap_user, fame_config.ldap_password)
    except ldap.INVALID_CREDENTIALS:
        print "Cannot connect to LDAP: invalid credentials"
        return None

    users = con.search_s(
        fame_config.ldap_filter_dn, ldap.SCOPE_SUBTREE,
        filterstr=fame_config.ldap_filter_email.format(email)
    )

    ldap_user = None

    if users:
        user = users[0][1]

        principal = user['userPrincipalName'][0].decode()
        full_name = user['cn'][0].decode()
        email = user['mail'][0].decode()
        enabled = (int(user['userAccountControl'][0].decode()) & 0x2) == 0
        groups = [group for group in map(
            lambda x: x.decode().lower().split(",")[0].lstrip("cn="),
            user['memberOf']
        )]

        ldap_user = {
            "principal": principal,
            "name": full_name,
            "mail": email,
            "enabled": enabled,
            "groups": groups
        }

    return ldap_user


def ldap_authenticate(email, password):
    con = _ldap_get_con()
    ldap_user = _find_user_by_email(con, email)

    if ldap_user:
        try:
            con.simple_bind_s(ldap_user['principal'], password)
            return ldap_user
        except ldap.INVALID_CREDENTIALS:
            # forward exception to view
            raise
        finally:
            con.unbind_s()


def auth_token(user):
    return codecs.encode(os.urandom(12), 'hex').decode() + make_secure_token(user['email'], os.urandom(32))


def password_reset_token(user):
    signer = TimestampSigner(fame_config.secret_key)

    return signer.sign(str(user['_id']))


def validate_password_reset_token(token):
    signer = TimestampSigner(fame_config.secret_key)

    return signer.unsign(token, max_age=86400).decode()


def get_mapping(collection, name):
    result = set()
    for source_group in collection:
        for mapping in ROLE_MAPPING.get(source_group, {}).get(name, []):
            result.update(mapping)
    return list(result)


def create_user(ldap_user):
    groups = get_mapping(ldap_user['groups'], "groups")
    default_sharing = get_mapping(ldap_user['groups'], "default_sharing")
    permissions = get_mapping(ldap_user["groups"], "permissions")

    user = User({
        'name': ldap_user['name'],
        'email': ldap_user['mail'],
        'enabled': ldap_user['enabled'],
        'groups': groups,
        'default_sharing': default_sharing,
        'permissions': permissions,
    })
    user.save()
    user.generate_avatar()

    return user


def update_or_create_user(ldap_user):
    user = User.get(email=ldap_user['mail'])

    if user:
        # update groups
        groups = get_mapping(ldap_user['groups'], "groups")
        user.update_value('groups', groups)

        # update default sharings
        default_sharing = get_mapping(ldap_user['groups'], "default_sharing")
        user.update_value('default_sharing', default_sharing)

        # update permissions
        permissions = get_mapping(ldap_user["groups"], "permissions")
        user.update_value('permissions', permissions)

        # enable/disable user
        user.update_value('enabled', ldap_user['enabled'])

        return user_if_enabled(user)

    return create_user(ldap_user)


def authenticate(email, password):
    ldap_user = ldap_authenticate(email, password)

    if not ldap_user:
        # user not found in LDAP, update local user object accordingly (if existent)
        user = User.get(email=email)
        if user:
            print "Disabling user {}: not available in LDAP".format(email)
            user.update_value('enabled', False)

        return user

    user = update_or_create_user(ldap_user)

    if user:
        login_user(user)

    return user
