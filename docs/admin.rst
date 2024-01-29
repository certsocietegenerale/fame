.. _admin:

*******************
Administrator Guide
*******************

If all went well during your installation, you should have a login page when accessing FAME.

.. image:: /images/login.png

Log in using the email address and password defined during installation. At the top right, click on your avatar to access the settings.

.. image:: /images/admin_avatar_menu.png

1. :ref:`user-account`
2. :ref:`admin-configuration`
3. :ref:`admin-users`

Click on 'Configuration' to configure your instance.

.. _admin-configuration:

Configuration options and module management
===========================================

Configurations
--------------

The first panel on this page is the 'Configurations' panel. It groups configuration options that are used directly by FAME, or used by several modules.

.. image:: /images/admin_configurations.png


Each configuration option have their own menus. Most options are self-explanatory and can be tuned based on your preferences. However, one specific configuration menu is directly used by FAME: types.

types
^^^^^

.. image:: /images/admin_types.png

This configuration is mandatory, but has a good default value. In order to correctly analyze files, FAME needs to first determine the file type. The file can be determined by the following elements, in this order of priority:

1. The extension, as specified in the `[extensions]` section.
2. The detailed type, as specified in the `[details]` section.
3. The mime type, as specified in the `[types]` section.

If no match was found, FAME will use the mime type.

.. note::
    When installing and enabling modules, be sure to correctly read displayed instructions. Some modules might need additional type mappings to work properly, in which case you will have to alter this configuration.


Module Repositories
-------------------

FAME relies on modules in order to add functionalities. Every module comes from a module repository, which is simply a git repository. You can have as many module repositories as you want, and this enables you to easily use modules created and shared by others.

.. image:: /images/admin_module_repositories.png

On a fresh installation, FAME comes with the community module repository already installed ``(1)``. Any repository that you configure can be:

* Updated ``(2)``: this will perform a ``git pull`` of the repository. This operation could add, remove or modify existing modules. New modules are disabled by default, and when a module changed too much its configuration options, it will also be disabled. All workers will automatically reload following an update, making sure that the updated code is used.
* Deleted ``(3)``: this will remove all files for this repository, and all modules that were in it will disappear. You can do this for all repositories, but it is not recommended to delete the `community` repository that is installed by default, because some other repositories might depend on it.

The `Reload` button ``(4)`` is only useful when you are making local changes to modules. It will reload all modules from disk and make sure all workers are restarted.

Adding a new repository
^^^^^^^^^^^^^^^^^^^^^^^

Following the `Add repository` link ``(5)`` will take you to a new window that you can use to add repositories.

.. image:: /images/admin_new_module_repository.png

You need to give a name ``(1)`` to your repository. This will be used as a folder and package name in your installation. You should only use valid Python package names (https://www.python.org/dev/peps/pep-0008/#package-and-module-names).

The address ``(2)`` is the URL of the git repository to add. It is basically what you would use at the end of a ``git clone`` command. You can use the SSH or HTTP URL of the repository, but SSH is mandatory for private repositories.

When using a private repository, check the `Private` checkbox ``(3)``. This will display additional information regarding how you should configure you repository. FAME generates an SSH key on installation, which has to be used in order to access private repositories.

.. warning::
    You have to make sure that the SSH key displayed has access to your private repository. This can be achieved in several ways. The easiest way is to configure a `Deploy Key <https://developer.github.com/guides/managing-deploy-keys/#deploy-keys>`_ on your repository.

    However, you will not be able to use this technique more than once, so it will not work if you need to add several private repositories. In this case, you should use a `Machine User <https://developer.github.com/guides/managing-deploy-keys/#machine-users>`_.

Once your repository is added, modules will automatically appear, and you will be able to enable them.

Modules
-------

All modules added by module repositories are listed below `Module Repositories`, grouped by module type (Processing, Antivirus, Threat Intelligence and Reporting).

.. image:: /images/admin_module_list.png

Each block has the following information:

* The name of the module ``(1)``
* A description of what it does ``(2)``
* Optional: a list of file types on which the module can act ``(3)``
* Optional: a list of triggers (matching tags in order to determine when this module will be executed) ``(4)``
* Optional: a list of file types that can be generated by this module ``(5)``
* The queue, which defines on which worker the module will be executed ``(6)``
* The current state of the module (enabled / disabled) ``(7)``

There is also two buttons that you can use to configure the module ``(8)`` and alter its state ``(9)``.

Module Configuration
^^^^^^^^^^^^^^^^^^^^

Clicking on the `Configure` button will take you to the configuration page for this module.

.. image:: /images/admin_module_configuration.png

The first three elements can be defined for all processing modules:

* Acts On ``(1)``: define the list of FAME types this module can execute on. This list is comma-separated.
* Triggered By ``(2)``: comma-delimited list of `fnmatch <https://docs.python.org/2/library/fnmatch.html>`_ patterns that will be matched against tags generated by analysis in order to determine when the module should be executed.
* Queue ``(3)``: defines on which workers this module will execute. By default, Worker are using the `unix` or `windows` queues, depending on the platform, but this can be changed to suit your needs. Changing the `queue` will make all workers restart automatically.

Then, each module has the possibility of defining any number of settings ``(4)``. Required settings are marked with a ``*``. If a setting has a default value, it will be displayed as a placeholder.

These settings are all applied globally, except when the `option` checkbox ``(5)`` is checked. In this case, this setting will be available for the user, at submission time, enabling users to define per-analysis values.

.. _admin-users:

Managing Local Users
====================

This section lets you manage users that have access to FAME.


When using the local authentication method, you are presented with a list of existing users:

.. image:: /images/admin_users.png

On a fresh install, you will have only your administrator account created, an optionally an account named "FAME Worker" ``(1)``. This account is needed when using remote workers, so you should not delete or disable it.

From the list of users, you can disable ``(2)`` or enable ``(3)`` a user. A disabled user cannot log in to your FAME instance. Disabled user accounts are automatically deleted after 30 days, based on their last activity.

Clicking on the name of a user will let you :ref:`admin-user-edit`.

Clicking on the top right button ``(4)`` will allow you to :ref:`admin-user-create`.

.. _admin-user-create:

Create a new user account
-------------------------

.. image:: /images/admin_new_user.png

When creating a new user, you have to specify the user's full name ``(1)``, his email address ``(2)``, but also the groups it belongs to ``(3)``. An user can belong to as many group as you want, and groups do not have to be defined previously.

You can also assign permissions ``(4)`` to the user. Permissions are used to give access to certain FAME features. Modules have the possibility to define their own permissions. The special ``*`` permission grants all present and future permissions.

.. warning::
    Granting the `MANAGE_USERS` permission to a user is almost the same as giving him all permissions, since he will be able to define his own permissions.

When you have finished creating the user by clicking on the `Create` button, an email will be sent to the user with a link to define his password.

If this feature is disabled (because email is not correctly configured), a link will be displayed with the password reset link, that you should send to the user.

.. note::
    If external authentication methods are enabled (LDAP, OIDC, etc...), users will be created automatically during their first successful connection attempt.

.. _admin-user-edit:

Edit a user account
-------------------

When clicking on the full name of a user, you will be able to edit his account.

The first half of this page is similar to the one used to :ref:`admin-user-create`. The other half is similar to the :ref:`user-account`.

.. warning::
  If external authentication methods are enabled (LDAP, OIDC, etc...), editing users directly is pointless as the edited data will be overridden by the external source during next user connection attempt.
