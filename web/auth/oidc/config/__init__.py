try:
    from .custom_mappings import *
except ModuleNotFoundError:
    from fame.common.exceptions import MissingConfiguration

    raise MissingConfiguration(
        "Missing OpenID Connect mapping file. Please check if file web/auth/oidc/config/custom_mappings.py exists."
    )
