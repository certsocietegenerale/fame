import os
from io import BytesIO
from shutil import move, rmtree
from time import time
from zipfile import ZipFile
from flask import url_for, request, flash, make_response
from flask_classy import FlaskView, route
from uuid import uuid4
from markdown2 import markdown

from web.views.negotiation import render, redirect, validation_error
from web.views.mixins import UIView
from web.views.helpers import get_or_404, requires_permission, file_download, clean_modules, clean_repositories
from fame.common.config import fame_config
from fame.common.constants import FAME_ROOT, MODULES_ROOT
from fame.common.utils import get_class, tempdir
from fame.common.exceptions import MissingConfiguration
from fame.core.module import ModuleInfo
from fame.core.config import Config
from fame.core.repository import Repository
from fame.core.internals import Internals
from fame.core.module_dispatcher import dispatcher


def get_name(module):
    return module['name']


def get_deploy_key():
    # Public key comes as an env var when running as docker container
    if os.getenv("FAME_DOCKER", "0") == "1":
        return os.getenv("FAME_PUBLIC_KEY")

    keyfile = os.path.join(FAME_ROOT, "conf", "id_rsa.pub")

    key = None
    try:
        with open(keyfile, 'r') as fd:
            key = fd.read()
    except:
        pass

    return key


def get_module_readme(module):
    readme = module.get_file('README.md')

    if readme:
        with open(readme, 'r') as f:
            readme = markdown(f.read(), extras=["code-friendly"])

    return readme


def update_config(settings, options=False):
    for config in settings:
        value = request.form.get("config_{}".format(config['name']))

        if value == '':
            config['value'] = None
            if 'default' not in config:
                flash('{} is required'.format(config['name']), 'danger')
                return validation_error()
        else:
            if config['type'] == "bool":
                config['value'] = (value is not None) and (value not in ['0', 'False'])
            else:
                if value is None:
                    continue

                if config['type'] == "integer":
                    try:
                        config['value'] = int(value, 0)
                    except:
                        flash('{} must be an integer'.format(config['name']), 'danger')
                        return validation_error()
                else:
                    config['value'] = value

        if options:
            option = request.form.get("config_{}_option".format(config['name']))
            config['option'] = (option is not None) and (option not in ['0', 'False'])

    return None


class ModulesView(FlaskView, UIView):

    @requires_permission('manage_modules')
    def index(self):
        """Get the list of modules.

        .. :quickref: Module; Get the list of modules

        Requires the `manage_modules` permission.

        The response is a dict with several elements:

        * ``modules``, which is a list of modules, sorted by type::

            "modules": {
                "Antivirus": [
                    ...
                ],
                "Preloading": [
                    ...
                ],
                "Processing": [
                    {
                        "_id": {
                            "$oid": "MODULE_ID"
                        },
                        "acts_on": [
                            ACTS_ON_FAME_TYPES
                        ],
                        "class": "CLASS_NAME",
                        "config": [ CONFIG_OPTIONS ],
                        "description": "DESCRIPTION",
                        "enabled": false,
                        "generates": [GENERATES],
                        "name": "NAME",
                        "path": "MODULE_PATH",
                        "queue": "QUEUE",
                        "triggered_by": [
                            TRIGGERS
                        ],
                        "type": "Processing"
                    },
                    ...
                ],
                "Reporting": [
                    ...
                ],
                "Threat Intelligence": [
                    ...
                ],
                "Filetype": [
                    ...
                ]
            }

        * ``repositories``: list of configured repositories::

            "repositories": [
                {
                    "_id": {
                        "$oid": "ID"
                    },
                    "address": "git@github.com:certsocietegenerale/fame_modules.git",
                    "name": "community",
                    "private": false,
                    "status": "active"
                },
                ...
            ]

        * ``configs``: list of named configurations::

            "configs": [
                {
                    "_id": {
                        "$oid": "ID"
                    },
                    "config": [
                        {
                            "description": "List of patterns (strings) to look for in malware configurations. There should be one pattern per line.",
                            "name": "monitor",
                            "type": "text",
                            "value": null
                        }
                    ],
                    "description": "Needed in order to be able to track malware targets",
                    "name": "malware_config"
                },
                ...
            ]
        """
        types = {
            'Preloading': [],
            'Processing': [],
            'Reporting': [],
            'Threat Intelligence': [],
            'Antivirus': [],
            'Virtualization': [],
            'Filetype': []
        }

        for module in ModuleInfo.get_collection().find():
            types[module['type']].append(clean_modules(module))

        for type in types:
            types[type] = sorted(types[type], key=get_name)

        configs = Config.get_collection().find()

        repositories = clean_repositories(list(Repository.get_collection().find()))

        return render({'modules': types, 'configs': configs, 'repositories': repositories}, 'modules/index.html')

    @requires_permission('manage_modules')
    @route('/<id>/disable', methods=['POST'])
    def disable(self, id):
        """Disable a module

        .. :quickref: Module; Disable a module

        Requires the `manage_modules` permission.

        :param id: id of the module to disable.
        :>json Module module: resulting module.
        """
        module = ModuleInfo(get_or_404(ModuleInfo.get_collection(), _id=id))
        module.update_value('enabled', False)

        updates = Internals(get_or_404(Internals.get_collection(), name="updates"))
        updates.update_value("last_update", time())

        dispatcher.reload()

        return redirect({'module': clean_modules(module)}, url_for('ModulesView:index'))

    @requires_permission('manage_modules')
    @route('/<id>/enable', methods=['POST'])
    def enable(self, id):
        """Enable a module

        .. :quickref: Module; Enable a module

        Requires the `manage_modules` permission.

        If successful, will return the module in ``module``.
        Otherwise, errors will be available in ``errors``.

        :param id: id of the module to enable.
        """
        module = ModuleInfo(get_or_404(ModuleInfo.get_collection(), _id=id))

        if 'error' in module:
            flash("Cannot enable '{}' because of errors installing dependencies.".format(module['name']), 'danger')
            return validation_error(url_for('ModulesView:index'))

        # See if module is properly configured
        module_class = get_class(module['path'], module['class'])
        module_class.info = module
        try:
            module_class()
        except MissingConfiguration, e:
            if e.name:
                flash("You must configure '{}' before trying to enable '{}'".format(e.name, module['name']), 'warning')
                return validation_error(url_for('ModulesView:configuration', id=e.id))
            else:
                flash("You must configure '{}' before trying to enable it.".format(module['name']), 'warning')
                return validation_error(url_for('ModulesView:configure', id=module['_id']))

        module.update_value('enabled', True)

        updates = Internals(get_or_404(Internals.get_collection(), name="updates"))
        updates.update_value("last_update", time())

        dispatcher.reload()

        readme = get_module_readme(module)
        if readme:
            flash(readme, 'persistent')

        return redirect({'module': clean_modules(module)}, url_for('ModulesView:index'))

    @requires_permission('manage_modules')
    @route('/<id>/configuration', methods=['GET', 'POST'])
    def configuration(self, id):
        """Configure a named configuration.

        .. :quickref: Module; Configure a named configuration

        Requires the `manage_modules` permission.

        For each configuration available, you should set the value in a form
        parameter named ``config_NAME``. For boolean values, any value not ``0``
        or ``False`` is considered to be ``True``.

        If successful, will return the named configuration in ``config``.
        Otherwise, errors will be available in ``errors``.

        :param id: id of the named configuration.
        """
        config = Config(get_or_404(Config.get_collection(), _id=id))

        if request.method == "POST":
            errors = update_config(config['config'])
            if errors is not None:
                return errors

            config.save()
            dispatcher.reload()
            return redirect({'config': config}, url_for('ModulesView:index'))
        else:
            return render({'config': config}, 'modules/configuration.html')

    @requires_permission('manage_modules')
    @route('/<id>/configure', methods=['GET', 'POST'])
    def configure(self, id):
        """Configure a module.

        .. :quickref: Module; Configure a module

        Requires the `manage_modules` permission.

        For each configuration available, you should set the value in a form
        parameter named ``config_NAME``. For boolean values, any value not ``0``
        or ``False`` is considered to be ``True``.

        If the setting should be an option (be available per analysis), you have
        to set ``config_NAME_option`` to any value but ``0`` or ``False``.

        If successful, will return the module in ``module``.
        Otherwise, errors will be available in ``errors``.

        :param id: id of the named configuration.

        :form acts_on: comma-delimited list of FAME types this module can act on
            (for Processing and Preloading modules).
        :form triggered_by: comma-delimited list of triggers (only for Processing
            modules).
        :form queue: name of the queue to use for this module (for Processing and
            Preloading modules).
        """

        def update_queue():
            new_queue = request.form.get('queue')

            if module['queue'] == '':
                flash('queue cannot be empty', 'danger')
                return validation_error()
            else:
                if module['queue'] != new_queue:
                    module.update_setting_value('queue', new_queue)
                    updates = Internals(get_or_404(Internals.get_collection(), name="updates"))
                    updates.update_value("last_update", time())

                    flash('Workers will reload once they are done with their current tasks', 'success')

        module = ModuleInfo(get_or_404(ModuleInfo.get_collection(), _id=id))
        module['readme'] = get_module_readme(module)

        if request.method == "POST":
            if module['type'] == 'Filetype':
                if 'acts_on' in request.form:
                    module.update_setting_value('acts_on', request.form.get('acts_on', ''))
            elif module['type'] == 'Processing':
                if 'acts_on' in request.form:
                    module.update_setting_value('acts_on', request.form.get('acts_on', ''))

                if 'triggered_by' in request.form:
                    module.update_setting_value('triggered_by', request.form.get('triggered_by', ''))

                if 'queue' in request.form:
                    update_queue()

            elif module['type'] == "Preloading":
                if "acts_on" in request.form:
                    module.update_setting_value('acts_on', request.form.get('acts_on', ''))

                if 'queue' in request.form:
                    update_queue()

            errors = update_config(module['config'], options=(module['type'] in ['Preloading', 'Processing']))
            if errors is not None:
                return errors

            module.save()
            dispatcher.reload()
            return redirect({'module': clean_modules(module)}, url_for('ModulesView:index'))
        else:
            return render({'module': clean_modules(module)}, 'modules/module_configuration.html')

    def list(self):
        """List enabled Processing modules

        .. :quickref: Module; List enabled Processing modules

        :>json list modules: list of enabled modules.
        """
        modules = ModuleInfo.get_collection().find({'enabled': True, 'type': {'$in': ['Processing', 'Preloading']}})

        return render(clean_modules(list(modules)))

    @requires_permission('manage_modules')
    @route('/reload', methods=['POST'])
    def reload(self):
        """Reload the workers

        .. :quickref: Module; Reload workers

        Requires the `manage_modules` permission.

        Returns "ok".
        """
        for repository in Repository.get_collection().find():
            dispatcher.update_modules(Repository(repository))

        updates = Internals(get_or_404(Internals.get_collection(), name="updates"))
        updates.update_value("last_update", time())

        flash('Workers will reload once they are done with their current tasks', 'success')

        return redirect('ok', url_for('ModulesView:index'))

    @requires_permission('manage_modules')
    @route('/repository/<id>/update', methods=['POST'])
    def repository_update(self, id):
        """Update a repository

        .. :quickref: Module; Update repository

        Requires the `manage_modules` permission.

        :param id: id of the repository.

        :>json Repository repository: the repository.
        """
        repository = Repository(get_or_404(Repository.get_collection(), _id=id))
        repository.update_files()

        return redirect({'repository': clean_repositories(repository)}, url_for('ModulesView:index'))

    @requires_permission('worker')
    @route('/repository/<id>/update', methods=['PUT'])
    def repository_receive_update(self, id):
        repository = Repository(
            get_or_404(Repository.get_collection(), _id=id))

        backup_path = os.path.join(fame_config.temp_path, 'modules_backup_{}'.format(uuid4()))

        # make sure, the path exists before we backup things;
        # prevents errors if the repository was not installed
        # prior to this 'update' request
        try:
            os.makedirs(repository.path())
        except OSError:
            pass

        try:
            move(repository.path(), backup_path)

            with ZipFile(BytesIO(request.data), 'r') as zipf:
                zipf.extractall(repository.path())

            repository['status'] = 'active'
            repository['error_msg'] = ''
            repository.save()

            dispatcher.update_modules(repository)

            updates = Internals(get_or_404(Internals.get_collection(), name="updates"))
            updates.update_value("last_update", time())

            rmtree(backup_path)

            return make_response('', 204)  # no response
        except Exception, e:
            print "[E] Could not update repository {}: {}".format(
                repository['name'], e)
            print "[E] Restoring previous version"
            rmtree(repository.path())
            move(backup_path, repository.path())

            repository['status'] = 'error'
            repository['error_msg'] = \
                "could not update repository: '{}'".format(e)

            import traceback
            traceback.print_exc()

            return validation_error()

    @requires_permission('manage_modules')
    @route('/repository/<id>/delete', methods=['POST'])
    def repository_delete(self, id):
        """Delete a repository

        .. :quickref: Module; Delete repository

        Requires the `manage_modules` permission.
        Returns "ok".

        :param id: id of the repository.
        """
        repository = Repository(get_or_404(Repository.get_collection(), _id=id))
        repository.delete()
        dispatcher.reload()

        return redirect('ok', url_for('ModulesView:index'))

    @requires_permission('manage_modules')
    @route('/repository/new', methods=['GET', 'POST'])
    def repository_new(self):
        """Add a repository

        .. :quickref: Module; Add repository

        Requires the `manage_modules` permission.

        If successful, will return the repository in ``repository``.
        Otherwise, errors will be available in ``errors``.

        :form name: name of the repository (should be a valid package name).
        :form address: HTTPs or SSH address of the repository.
        :form private: boolean specifying if the repository is private. See
            Administration Guide for more details on private repositories.
        """
        deploy_key = get_deploy_key()
        repository = Repository()

        if request.method == 'POST':
            for field in ['name', 'address']:
                repository[field] = request.form.get(field)
                if repository[field] is None or repository[field] == "":
                    flash("{} is required.".format(field), 'danger')
                    return validation_error()

                existing_repository = Repository.get(**{field: repository[field]})
                if existing_repository:
                    flash("There is already a repository with this {}.".format(field), 'danger')
                    return validation_error()

            value = request.form.get('private')
            repository['private'] = (value is not None) and (value not in ['0', 'False'])

            if repository['private'] and deploy_key is None:
                flash("Private repositories are disabled because of a problem with your installation (you do not have a deploy key in 'conf/id_rsa.pub')", 'danger')
                return validation_error()

            repository.save()
            repository.update_files()

            return redirect({'repository': clean_repositories(repository)}, url_for('ModulesView:index'))

        return render({'repository': repository, 'deploy_key': deploy_key}, 'modules/repository_new.html')

    @requires_permission('worker')
    @route('/download', methods=['GET'])
    def download(self):
        # First, create a zip file with the modules
        path = os.path.join(tempdir(), 'modules.zip')
        with ZipFile(path, 'w') as zipf:
            for root, dirs, files in os.walk(MODULES_ROOT):
                for filename in files:
                    # Ignore pyc files
                    if not filename.endswith('.pyc'):
                        filepath = os.path.join(root, filename)
                        zipf.write(filepath, os.path.relpath(filepath, MODULES_ROOT))

        # Return the zip file
        response = file_download(path)

        # Delete it
        os.remove(path)

        return response
