This module allow authenticating accounts using LDAP(S) against Windows AD server

*This module requires a Windows AD server and is not compatible with OpenLDAP servers.*

# Configuration

This authenticator requires several config values to set prior to using the authenticator. The settings are shown in the following table.  These settings need to be put into the fame config file.

| Name              | Description                                      | Example value                                           |
|-------------------|--------------------------------------------------|---------------------------------------------------------|
| ldap_uri          | The LDAP URI of the LDAP server.                 | `ldap://dc.ad-domain.com:389`                           |
| ldap_user         | The user that is used to access the LDAP server. | `username@ad-domain.com`                                |
| ldap_password     | The password for the LDAP user.                  | `password`                                              |
| ldap_filter_email | The LDAP filter query that selects user objects. | `(&(objectCategory=Person)(sAMAccountName=*)(mail={}))` |
| ldap_filter_dn    | The LDAP filter for the DN.                      | `OU=People,DC=ad-domain,DC=com`                         |

Then, you need to copy `fame/web/auth/ad/config/custom_mappings.py.sample` to `fame/web/auth/ad/config/custom_mappings.py`, and modify the file accordingly.

Finally, you need to set `auth=ad` in the config file to enable the authentication method. You can set up multiple authentication method, (e.g., `auth=ad user_password`) if you need to allow a fallback auth.
