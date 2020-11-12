from importlib import import_module
from flask import request, flash, url_for, abort
from flask_login import current_user
from flask_classful import FlaskView, route

from fame.common.config import fame_config
from fame.core.user import User
from fame.core.module_dispatcher import dispatcher
from web.views.mixins import UIView
from web.views.negotiation import render, redirect, validation_error
from web.views.helpers import requires_permission, get_or_404, clean_users


auth_module = import_module('web.auth.{}.views'.format(fame_config.auth))


class UsersView(FlaskView, UIView):
    @requires_permission('manage_users')
    def index(self):
        """Get all users.

        .. :quickref: User; Get the list of users

        Requires the `manage_users` permission.
        The result is in the ``users`` field.

        :>jsonarr ObjectId _id: user's ObjectId.
        :>jsonarr string name: full name.
        :>jsonarr string: email address.
        :>jsonarr boolean enabled: ``True`` if the user is enabled.
        :>jsonarr list groups: list of groups the user belongs to.
        :>jsonarr list default_sharing: list of groups used by the user as default sharing preferences.
        :>jsonarr list permissions: list of user's permissions
        """
        users = {"users": clean_users(list(User.find()))}

        return render(users, 'users/index.html')

    @requires_permission('manage_users')
    @route('/new', methods=['GET'])
    def new(self):
        context = {'user': {}, 'permissions': dispatcher.permissions}

        return render(context, 'users/new.html')

    def _valid_form(self, name, email, groups, previous_email=None):
        for var in ['name', 'email', 'groups']:
            if not locals()[var]:
                flash('"{}" is required'.format(var), 'danger')
                return False

        if (previous_email is None) or (previous_email != email):
            existing_user = User.get_collection().find_one({'email': email})
            if existing_user:
                flash('User with email "{}" already exists.'.format(email), 'danger')
                return False

        return True

    def get_permissions(self, current_permissions=[]):
        current_permissions = set(current_permissions)

        for permission in dispatcher.permissions:
            value = request.form.get("permission_{}".format(permission))

            if (value is not None) and (value not in ['0', 'False']):
                current_permissions.add(permission)
            else:
                current_permissions.discard(permission)

        return list(current_permissions)

    @requires_permission('manage_users')
    @route('/create', methods=['POST'])
    def create(self):
        """Create a user.

        .. :quickref: User; Create new user

        Requires the `manage_users` permission.

        When succesful, the new user will be returned in the ``user`` field.
        Otherwise, an ``errors`` field will list errors.

        :form name: full name
        :form email: email address
        :form groups: comma-delimited list of groups
        :form permission_VALUE: specify a value different than ``0`` or ``False``
            for all permissions the user should have.
        """
        name = request.form.get('name')
        email = request.form.get('email').lower()
        groups = [g for g in request.form.get('groups', '').split(',') if g]

        if not self._valid_form(name, email, groups):
            return validation_error()

        user = User({
            'name': name,
            'email': email.lower(),
            'groups': groups,
            'default_sharing': groups,
            'permissions': self.get_permissions(),
            'enabled': True
        })

        if not auth_module.create_user(user):
            return validation_error()

        user.save()

        return redirect({'user': clean_users(user)}, url_for('UsersView:index'))

    @requires_permission('manage_users')
    @route('/<id>/update', methods=['POST'])
    def update(self, id):
        """Update a user.

        .. :quickref: User; Update existing user

        Requires the `manage_users` permission.

        When succesful, the new user will be returned in the ``user`` field.
        Otherwise, an ``errors`` field will list errors.

        :form name: full name
        :form email: email address
        :form groups: comma-delimited list of groups
        :form permission_VALUE: specify a value different than ``0`` or ``False``
            for all permissions the user should have.
        """
        name = request.form.get('name')
        email = request.form.get('email').lower()
        groups = [g for g in request.form.get('groups', '').split(',') if g]

        user = User(get_or_404(User.get_collection(), _id=id))

        if not self._valid_form(name, email, groups, user['email']):
            return validation_error()

        user['name'] = name
        user['email'] = email
        user['groups'] = groups
        user['permissions'] = self.get_permissions(user['permissions'])
        user.save()

        return redirect({'user': clean_users(user)}, url_for('UsersView:get', id=user['_id']))

    @requires_permission('manage_users')
    @route('/<id>/enable', methods=['POST'])
    def enable(self, id):
        """Enable a user.

        .. :quickref: User; Enable a user

        Requires the `manage_users` permission.

        :param id: user id.

        :>json User user: modified user.
        """
        user = User(get_or_404(User.get_collection(), _id=id))
        user.update_value('enabled', True)

        return redirect({'user': clean_users(user)}, url_for('UsersView:index'))

    @requires_permission('manage_users')
    @route('/<id>/disable', methods=['POST'])
    def disable(self, id):
        """Disable a user.

        .. :quickref: User; Disable a user

        Requires the `manage_users` permission.

        :param id: user id.

        :>json User user: modified user.
        """
        user = User(get_or_404(User.get_collection(), _id=id))
        user.update_value('enabled', False)

        return redirect({'user': clean_users(user)}, url_for('UsersView:index'))

    def ensure_permission(self, id):
        if not ((str(current_user['_id']) == id) or current_user.has_permission('manage_users')):
            abort(403)

    def get(self, id):
        """Get a user.

        .. :quickref: User; Get a user

        The user is returned in the ``user`` field.

        :param id: user id

        :>json ObjectId _id: user's ObjectId.
        :>json string name: full name.
        :>json string: email address.
        :>json boolean enabled: ``True`` if the user is enabled.
        :>json list groups: list of groups the user belongs to.
        :>json list default_sharing: list of groups used by the user as default sharing preferences.
        :>json list permissions: list of user's permissions
        """
        self.ensure_permission(id)
        user = User(get_or_404(User.get_collection(), _id=id))

        return render({'user': clean_users(user), 'permissions': dispatcher.permissions}, 'users/profile.html')

    @route('/<id>/default_sharing', methods=['POST'])
    def default_sharing(self, id):
        """Change a user's default sharing.

        .. :quickref: User; Change default sharing

        When used on another user account, requires the `manage_users` permission.

        :param id: user id.

        :>json User user: modified user.
        """
        self.ensure_permission(id)

        user = User(get_or_404(User.get_collection(), _id=id))
        groups = request.form.get('groups', '').split(',')

        for group in groups:
            if group in user['groups']:
                break
        else:
            flash('You have to at least keep one of your groups.', 'danger')
            return redirect(request.referrer)

        user.update_value('default_sharing', groups)

        return redirect({'user': clean_users(user)}, request.referrer)

    @route('/<id>/reset_api', methods=['POST'])
    def reset_api(self, id):
        """Reset a user's API key.

        .. :quickref: User; Reset API key

        When used on another user account, requires the `manage_users` permission.

        :param id: user id.

        :>json User user: modified user.
        """
        self.ensure_permission(id)

        user = User(get_or_404(User.get_collection(), _id=id))
        user.update_value('api_key', User.generate_api_key())

        return redirect({'user': clean_users(user)}, request.referrer)
