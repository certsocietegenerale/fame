# Introduction

This module allows authenticating accounts using two OpenID connect flows: `authorization code` (for user authentication) and `client credentials` (for API/machine-to-machine authentication).

# Configuration

In order to use this module, you need to define several settings in the FAME config file. This file can be found in `conf/fame.conf` in your system (or in `utils/templates/local_fame.conf` on the Github repository)


| Name                    | Description                                                                                                                                                                  | Example value                                                                   |
|-------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| oidc_authorize_endpoint | URL of the `authorize` endpoint of your OpenID Connect Provider (OP). Unauthenticated users will be redirected to this endpoint to authenticate themselves                     | `https://opURL/oauth2/authorize`                                              |
| oidc_token_endpoint     | URL of the `access_token` endpoint of your OpenID Connect Provider (OP). This endpoint is used to verify the response given by the authorize endpoint.                         | `https://opURL/oauth2/access_token` or sometimes `https://opURL/oauth2/token` |
| oidc_userinfo_endpoint  | URL of the `userinfo` endpoint of your OpenID Connect Provider (OP). This endpoint is used to retrieve user information (name, email, etc) and permissions.                    | `https://opURL/oauth2/userinfo`                                               |
| oidc_tokeninfo_endpoint | URL of the `introspect` endpoint of your OpenID Connect Provider (OP). This endpoint is used for API logins, to retrieve token information (name, email, etc) and permissions. | `https://opURL/oauth2/introspect`                                             |
| oidc_requested_scopes   | Scopes (Permissions) which FAME users and tokens may have. FAME will request these scopes to the OP in order to find users/tokens permissions.                                 | `openid profile fame`, or sometimes `openid profile https://fameURL/`         |
| oidc_client_id          | Client ID of your FAME application.                                                                                                                                            | `11111111-1111-1111-1111-111111111111`                                        |
| oidc_client_secret      | Password associated with the Client ID.                                                                                                                                        | `ARandomClientSecret`                                                         |

When creating a client ID on the OP, you may be asked if you want to create a Confidential Client or a Public client. FAME requires a Confidential Client ID.

Also, you may be asked to provide a redirect URI. The redirect URI of FAME is `{fame_root}/login-oidc`.


Then, you need to copy `web/auth/oidc/config/custom_mappings.py.sample` to `web/auth/oidc/config/custom_mappings.py`, and modify the file accordingly. 

3 settings need to be set in this file:

| Setting            | Description                                                                                                                                                                                          |
|--------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| USER_CLAIM_MAPPING | Define which claim will be used by FAME to retrieve a user email, name or role. The claims are retrieved using the `userinfo` endpoint. JSONPath can be used in this field, if you need it.          |
| API_CLAIM_MAPPING  | Define which claim will be used by FAME to retrieve an API account email, name or role. The claims are retrieved using the `tokeninfo` endpoint. JSONPath can be used in this field, if you need it. |
| ROLE_MAPPING       | Map OpenID role(s) to FAME permissions, groups and default sharing. Note that one user may be granted multiple roles.                                                                                |

These 3 settings have to be defined in accordance with your OpenID provider (Claims are not standardized across OPs).

Finally, you need to set `auth=oidc` in the config file to enable the authentication method. You can set up multiple authentication method, (e.g., `auth=oidc user_password`) if you need to allow a fallback auth.

One note regarding the API: authentications to the FAME API using local FAME tokens will always be working, even if `auth` doesn't contain `user_password` in `fame.conf`.

# Custom CA file

HTTPS requests to the OP are made using `requests`, which check for certificate validity using `certifi`. Thus, if you have a custom or self-signed CA you need to add it to the certifi list.

You can find the location of this list on your system with the command `python3 -m requests.certs`. On Debian/Ubuntu, the certifi list can be found at `/etc/ssl/certs/ca-certificates.crt`
