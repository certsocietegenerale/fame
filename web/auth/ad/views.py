import ldap3
from flask import Blueprint, render_template, request, redirect, flash
from flask_login import logout_user
from fame.common.config import fame_config
from urllib.parse import urljoin

from web.views.helpers import prevent_csrf, user_has_groups_and_sharing, get_fame_url
from web.auth.ad.user_management import (
    authenticate,
    LdapSettingsNotPresentException,
    LdapGenericError,
)


auth = Blueprint("auth", __name__, template_folder="templates")


@auth.route("/ad-login", methods=["GET", "POST"])
@prevent_csrf
def login():
    if request.method == "GET":
        return render_template("login-ad.html")
    else:
        try:
            user = authenticate(request.form.get("email"), request.form.get("password"))
        except (
            ldap3.core.exceptions.LDAPExceptionError,
            ldap3.core.exceptions.LDAPSocketReceiveError,
            ldap3.core.exceptions.LDAPSocketSendError,
            ConnectionResetError,
        ) as e:
            if hasattr(e, "message"):
                flash(
                    "Cannot connect to the LDAP server: {}".format(e.message), "danger"
                )
            else:
                flash("Cannot connect to the LDAP server: {}".format(e), "danger")
            return render_template("login-ad.html")
        except LdapGenericError as e:
            flash("Error: {}".format(e.args[0]), "danger")
            return render_template("login-ad.html")
        except ldap3.core.exceptions.LDAPInvalidCredentialsResult as e:
            flash("Invalid credentials.", "danger")
            return render_template("login-ad.html")
        except LdapSettingsNotPresentException:
            flash("LDAP Settings not present. Check server logs.", "danger")
            return render_template("login-ad.html")

        if not user or not user_has_groups_and_sharing(user):
            flash("Access not allowed.", "danger")
            return render_template("login-ad.html")

        redir = request.args.get("next", "/")
        return redirect(urljoin(get_fame_url(), redir))


@auth.route("/logout")
def logout():
    logout_user()
    return redirect(urljoin(get_fame_url(), "/ad-login"))
