# Installation

The AD authentication module requires the python-ldap package to be available to FAME. It can be installed with this command: `utils/run.sh -m pip install python-ldap~=3.2.0`. This installs the required package into the virtualenv that is used by FAME.

Once installed, please change the authentication type of fame to "ad" if you want to use the AD authenticator.

# Configuration

This authenticator requires several config values to set prior to using the authenticator. The settings are shown in the following table.  These settings need to be put into the fame config file.

| Name  | Description|
|------|------------|
| ldap_uri | The LDAP URI of the LDAP server. Example: `ldap://dc.example.com` |
| ldap_user | The user that is used to access the LDAP server. |
| ldap_password | The password for the LDAP user. |
| ldap_filter_email | The LDAP filter query that selects user objects. Example query to select user objects by their email address: `(&(objectCategory=Person)(sAMAccountName=*)(mail={}))` |
| ldap_filter_dn | The LDAP filter for the DN. Example: `OU=People,DC=example,DC=com`|


# Custom CA files

python-ldap uses the system certificate storage to check for CA files. Thus, if you have a custom or self-signed CA you need to install it in the system and update the certificate store. Instructions for Ubuntu are:
```bash
cp <your_ca_file> /usr/local/share/ca-certificates/
update-ca-certificates
```
