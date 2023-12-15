import urllib.parse
import os
import uuid
import requests
from importlib import import_module
from flask import Blueprint, request, redirect, session, render_template
from flask_login import logout_user

from fame.core.user import User
from web.views.helpers import prevent_csrf, before_first_request, user_if_enabled, get_fame_url
from fame.common.config import fame_config
from web.auth.oidc.user_management import (
    authenticate_user,
    authenticate_api,
    check_oidc_settings_present,
    ClaimMappingError,
)

auth = Blueprint("", __name__, template_folder="templates")


@auth.route("/oidc-login", methods=["GET", "POST"])
@prevent_csrf
def login():
    check_oidc_settings_present()
    code = request.args.get("code", "")
    if code:
        auth = (fame_config.oidc_client_id, fame_config.oidc_client_secret)
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": get_fame_url() + "/oidc-login",
        }
        try:
            token = requests.post(
                fame_config.oidc_token_endpoint, auth=auth, data=data
            ).json()
        except requests.exceptions.RequestException as e:
            return render_template(
                "auth_error.html",
                error_description=f"Unable to contact the OIDC server: %s. If you are a FAME administrator, please check the value of oidc_token_endpoint."
                % e.args[0],
            )

        if not "access_token" in token:
            # invalid "code" given, invalid clientID/Secret in config, etc..
            error_description = token.get("error_description", "")
            return render_template(
                "auth_error.html", error_description=error_description
            )
        try:
            authenticate_user(token["access_token"])
            if session.get("_flashes"):
                session["_flashes"].clear()  # Clear any message asking to log in

            redir = request.args.get("next", "/")
            return redirect(urllib.parse.urljoin(get_fame_url(), redir))

        except ClaimMappingError as e:
            return render_template("auth_error.html", error_description=e.msg)
    else:
        args = {
            "client_id": fame_config.oidc_client_id,
            "response_type": "code",
            "scope": fame_config.oidc_requested_scopes,
            "redirect_uri": get_fame_url() + "/oidc-login",
            "nonce": uuid.uuid4().hex,
        }
        login_url = (
            fame_config.oidc_authorize_endpoint + "?" + urllib.parse.urlencode(args)
        )
        return redirect(login_url)


@auth.route("/logout")
def logout():
    logout_user()
    return render_template("logout.html")


# Override login_manager.request_loader to include authentication via client credentials flow
def override_request_loader(app):
    def api_auth(request):
        api_key = request.headers.get("X-API-KEY")
        oidc_token = request.headers.get("Autorization")
        user = User.get(api_key=api_key)

        if user:
            user.is_api = True
        elif oidc_token and oidc_token.lower().startswith("bearer "):
            args = {"access_token": oidc_token[7:]}
            tokeninfo_url = (
                fame_config.oidc_tokeninfo_endpoint + "?" + urllib.parse.urlencode(args)
            )
            try:
                tokeninfo = requests.get(tokeninfo_url).json()
            except requests.exceptions.RequestException as e:
                print(
                    "WARNING: Unable to contact the OIDC server: %s. Please check the value of oidc_tokeninfo_endpoint"
                    % e.args[0]
                )
                return False

            if not "error" in tokeninfo.keys():
                user = authenticate_api(tokeninfo)
                user.is_api = True

        return user_if_enabled(user)

    app.login_manager.request_loader(api_auth)


before_first_request.register(override_request_loader)
