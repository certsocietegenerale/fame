import os
from urlparse import urljoin
from zxcvbn import password_strength
from flask import Blueprint, render_template, request, redirect, flash, url_for
from flask_login import logout_user, current_user, login_required
from itsdangerous import BadTimeSignature, SignatureExpired
from werkzeug.security import check_password_hash

from fame.common.config import fame_config
from fame.common.email_utils import EmailServer
from fame.core.user import User
from web.views.helpers import prevent_csrf, get_or_404
from web.auth.user_password.user_management import authenticate, change_password, password_reset_token, validate_password_reset_token

auth = Blueprint('auth', __name__, template_folder='templates')

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def create_user(user):
    user.save()

    user.generate_avatar()

    token = password_reset_token(user)
    reset_url = urljoin(fame_config.fame_url, url_for('auth.password_reset', token=token))
    email_server = EmailServer(TEMPLATES_DIR)

    if email_server.is_connected:
        msg = email_server.new_message_from_template("Define your FAME account's password.", 'mail_user_creation.html', {'user': user, 'url': reset_url})
        msg.send([user['email']])
    else:
        if email_server.is_configured:
            error = "Could not connect to SMTP Server."
        else:
            error = "SMTP Server not properly configured."

        error += " The new user should visit '{}' in the next 24 hours in order to define his password".format(reset_url)
        flash(error, 'persistent')

    return True


def valid_new_password(password, confirmation):
    strength = password_strength(password)

    if password != confirmation:
        flash('Password confirmation differs from new password.', 'danger')
        return False
    elif strength['score'] <= 2:
        flash('New password is too weak. Estimated cracking time is {}.'.format(strength['crack_time_display']), 'danger')
        return False

    return True


@auth.route('/password_reset_form', methods=['GET', 'POST'])
@prevent_csrf
def password_reset_form():
    email_server = EmailServer(TEMPLATES_DIR)

    if email_server.is_connected:
        if request.method == 'POST':
            email = request.form.get('email')

            if not email:
                flash('You have to specify an email address', 'danger')
            else:
                user = User.get(email=email)

                if user:
                    token = password_reset_token(user)
                    reset_url = urljoin(fame_config.fame_url, url_for('auth.password_reset', token=token))

                    msg = email_server.new_message_from_template("Reset your FAME account's password.", 'mail_reset_password.html', {'user': user, 'url': reset_url})
                    msg.send([user['email']])

                flash('A password reset link was sent.')
                return redirect('/login')

        return render_template('password_reset_form.html')
    else:
        flash('Functionnality unavailable. Contact your administrator', 'danger')
        return redirect('/login')


@auth.route('/password_reset/<token>', methods=['GET', 'POST'])
@prevent_csrf
def password_reset(token):
    try:
        user_id = validate_password_reset_token(token)
    except BadTimeSignature:
        flash('Invalid token', 'danger')
        return redirect('/login')
    except SignatureExpired:
        flash('Expired token', 'danger')
        return redirect('/login')

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('password_confirmation', '')

        if valid_new_password(password, confirm):
            user = User(get_or_404(User.get_collection(), _id=user_id))
            change_password(user, password)
            flash('Password was successfully changed.', 'success')
            return redirect('/login')

    return render_template('password_reset.html')


@auth.route('/login', methods=['GET', 'POST'])
@prevent_csrf
def login():
    if request.method == 'GET':
        return render_template('login.html')
    else:
        if authenticate(request.form.get('email'), request.form.get('password')):
            redir = request.args.get('next', '/')
            return redirect(redir)
        else:
            flash("Invalid credentials.", "danger")
            return render_template('login.html')


@auth.route('/logout')
def logout():
    logout_user()
    return redirect('/login')


@auth.route('/change_password', methods=['POST'])
@prevent_csrf
@login_required
def _change_password():
    current = request.form.get('current_password', '')
    new = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')

    if not check_password_hash(current_user['pwd_hash'], current):
        flash('Current password is invalid', 'danger')
    elif valid_new_password(new, confirm):
        change_password(current_user, new)
        flash('Password was successfully changed.', 'success')

    return redirect(request.referrer)
