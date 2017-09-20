import os
import requests
from StringIO import StringIO
from shutil import copyfileobj
from hashlib import md5
from pymongo import DESCENDING
from flask import render_template, url_for, request, flash, make_response, abort, jsonify
from flask_login import current_user
from flask_classy import FlaskView, route
from flask_paginate import Pagination
from werkzeug.utils import secure_filename

from fame.common.exceptions import MissingConfiguration
from fame.common.config import fame_config
from fame.core.module_dispatcher import dispatcher
from fame.core.store import store
from fame.core.file import File
from fame.core.config import Config
from fame.core.analysis import Analysis
from fame.core.module import ModuleInfo
from web.views.negotiation import render, redirect, validation_error
from web.views.constants import PER_PAGE
from web.views.helpers import file_download, get_or_404, requires_permission, clean_analyses, clean_files, clean_users
from web.views.mixins import UIView


def get_options():
    options = {}

    for option_type in ['str', 'integer', 'text']:
        for option in dispatcher.options[option_type]:
            value = request.form.get("options[{}]".format(option))

            if value is None:
                flash('Missing option: {}'.format(option), 'danger')
                return None

            if option_type == 'integer':
                try:
                    options[option] = int(value, 0)
                except:
                    flash('{} must be an integer'.format(option), 'danger')
                    return None
            else:
                options[option] = value

    for option in dispatcher.options['bool']:
        value = request.form.get("options[{}]".format(option))
        options[option] = (value is not None) and (value not in ['0', 'False'])

    return options


class AnalysesView(FlaskView, UIView):
    def index(self):
        """Get the list of analyses.

        .. :quickref: Analysis; Get the list of analyses

        Response is paginated and will only contain 25 results. The most recent
        analyses appear first.

        :query page: page number.
        :type page: int

        :>json list analyses: list of analyses (see :http:get:`/analyses/(id)` for details on the format of an analysis).
        """
        page = int(request.args.get('page', 1))

        analyses = current_user.analyses.find().sort('_id', DESCENDING).limit(PER_PAGE).skip((page - 1) * PER_PAGE)
        pagination = Pagination(page=page, per_page=PER_PAGE, total=analyses.count(), css_framework='bootstrap3')
        analyses = {'analyses': clean_analyses(list(analyses))}
        for analysis in analyses['analyses']:
            file = current_user.files.find_one({'_id': analysis['file']})
            analysis['file'] = clean_files(file)

            if 'analyst' in analysis:
                analyst = store.users.find_one({'_id': analysis['analyst']})
                analysis['analyst'] = clean_users(analyst)

        return render(analyses, 'analyses/index.html', ctx={'data': analyses, 'pagination': pagination})

    def get(self, id):
        """Get the analysis with `id`.

        .. :quickref: Analysis; Get an analysis

        Resulting object is in the ``analysis`` field.

        :param id: id of the analysis.

        :>json dict _id: ObjectId dict.
        :>json dict analyst: analyst's ObjectId.
        :>json dict date: date dict.
        :>json list executed_modules: list of executed modules.
        :>json list pending_modules: list of pending modules.
        :>json list waiting_modules: list of waiting modules.
        :>json list canceled_modules: list of canceled modules.
        :>json list executed_modules: list of executed modules.
        :>json string module: the name of the target module.
        :>json string status: status of the analysis (one of `pending`, `running`, `finished` or `error`).
        :>json list tags: the list of tags.
        :>json list probable_names: the list of probable names.
        :>json list iocs: list of dict describing observables.
        :>json dict results: detailed results for each module, with the module name being the key.
        :>json dict generated_files: a dict of generated files, the key being the file type.
        :>json list extracted_files: a list of extracted files.
        :>json dict support_files: a dict of support files, the key being the module name.
        """
        analysis = {'analysis': clean_analyses(get_or_404(current_user.analyses, _id=id))}
        file = current_user.files.find_one({'_id': analysis['analysis']['file']})
        analysis['analysis']['file'] = clean_files(file)
        ti_modules = [m.name for m in dispatcher.get_threat_intelligence_modules()]
        av_modules = [m.name for m in dispatcher.get_antivirus_modules()]

        if 'extracted_files' in analysis['analysis']:
            files = []
            for id in analysis['analysis']['extracted_files']:
                files.append(current_user.files.find_one({'_id': id}))
            analysis['analysis']['extracted_files'] = clean_files(files)

        modules = dict()
        for module in ModuleInfo.get_collection().find():
            modules[module['name']] = ModuleInfo(module)

        return render(analysis, 'analyses/show.html', ctx={
            'analysis': analysis,
            'modules': modules,
            'av_modules': av_modules,
            'ti_modules': ti_modules
        })

    def new(self):
        config = Config.get(name="virustotal")

        hash_capable = False
        if config:
            try:
                config.get_values()
                hash_capable = True
            except:
                hash_capable = False

        return render_template('analyses/new.html', hash_capable=hash_capable, options=dispatcher.options)

    def _validate_form(self, groups, module):
        for group in groups:
            if group in current_user['groups']:
                break
        else:
            flash('You have to at least share with one of your groups.', 'danger')
            return False

        if module:
            if not ModuleInfo.get(name=module):
                flash('"{}" is not a valid module'.format(module), 'danger')
                return False

        return True

    def _get_object_to_analyze(self):
        file = request.files.get('file') or None
        url = request.form.get('url') or None
        hash = request.form.get('hash') or None

        f = None
        if file:
            f = File(filename=file.filename, stream=file.stream)
        elif url:
            stream = StringIO(url)
            f = File(filename='url', stream=stream)
            if not f.existing:
                f.update_value('type', 'url')
                f.update_value('names', [url])
        elif hash:
            config = Config.get(name="virustotal")
            if config:
                try:
                    config = config.get_values()

                    params = {'apikey': config.api_key, 'hash': hash}
                    response = requests.get('https://www.virustotal.com/vtapi/v2/file/download', params=params)
                    if response.status_code == 403:
                        flash('This requires a valid API key.', 'danger')
                    elif response.status_code == 404:
                        flash('No file found with this hash.', 'danger')
                    elif response.status_code == 200:
                        f = File(filename='{}.bin'.format(hash), stream=StringIO(response.content))
                except MissingConfiguration:
                    flash("VirusTotal is not properly configured.", 'danger')
            else:
                flash("There seems to be a problem with your installation (no 'virustotal' configuration)", 'danger')
        else:
            flash('You have to submit a file, a URL or a hash', 'danger')

        return f

    def post(self):
        """Create a new analysis.

        .. :quickref: Analysis; Create an analysis

        Launch a new analysis. You have to specify on which object this analysis
        will be made, by specifying one of:

        * ``file_id`` for an existing object
        * ``file`` for file uploads
        * ``url``
        * ``hash`` if VirusTotal sample retrieval is enabled.

        You should also supply all enabled analysis options with the name
        ``options[OPTION_NAME]``. For boolean options, any value different than
        ``0`` or ``False`` means the option is enabled.

        If the submitted object already exists (and ``file_id`` was not specified),
        the response will be a file object. When a new analysis was successfuly
        created, the analysis object will be returned, in the ``analysis`` field.

        If there was error in your submission, they will be returned in the
        ``errors`` field.

        **Example request**::

            headers = {
                'Accept': "application/json",
                'X-API-KEY': FAME_API_KEY
            }

            with open(filepath, 'rb') as f:
                params = {
                    'options[allow_internet_access]':  "on",
                    'options[analysis_time]': "300",
                    'groups': "cert"
                }

                files = {
                    'file': f
                }

                r = requests.post(ENDPOINT, data=params, files=files, headers=headers)

        :form string file_id: (optional) the id of the object on which this analysis should run.
        :form file file: (optional) file to analyze.
        :form string url: (optional) url to analyze.
        :form string hash: (optional) hash to analyze.
        :form string module: (optional) the name of the target module.
        :form string groups: a comma-separated list of groups that will have access to this analysis.
        :form string option[*]: value of each enabled option.
        """
        file_id = request.form.get('file_id')
        module = request.form.get('module') or None
        groups = request.form.get('groups', '').split(',')

        valid_submission = self._validate_form(groups, module)
        if not valid_submission:
            return validation_error()

        options = get_options()
        if options is None:
            return validation_error()

        if file_id is not None:
            f = File(get_or_404(current_user.files, _id=file_id))
            analysis = {'analysis': f.analyze(groups, current_user['_id'], module, options)}
            return redirect(analysis, url_for('AnalysesView:get', id=analysis['analysis']['_id']))
        else:
            f = self._get_object_to_analyze()
            if f is not None:
                f.add_owners(set(current_user['groups']) & set(groups))

                if f.existing:
                    f.add_groups(groups)
                    flash("File already exists, so the analysis was not launched.")

                    return redirect(clean_files(f), url_for('FilesView:get', id=f['_id']))
                else:
                    analysis = {'analysis': clean_analyses(f.analyze(groups, current_user['_id'], module, options))}
                    return redirect(analysis, url_for('AnalysesView:get', id=analysis['analysis']['_id']))
            else:
                return render_template('analyses/new.html', options=dispatcher.options)

    @requires_permission("submit_iocs")
    @route('/<id>/submit_iocs/<module>', methods=["POST"])
    def submit_iocs(self, id, module):
        """Submit observables to a Threat Intelligence module.

        .. :quickref: Analysis; Submit observables to a threat intelligence module

        If succesful, the response will be ``"ok"``.

        :param id: id of the analysis.
        :param module: name of the module to submit the file to.

        :<jsonarr string value: the value of the observable.
        :<jsonarr list tags: a list of tags associated to it.
        """
        analysis = Analysis(get_or_404(current_user.analyses, _id=id))

        for ti_module in dispatcher.get_threat_intelligence_modules():
            if ti_module.name == module:
                ti_module.iocs_submission(analysis, request.json)

        analysis.update_value(['threat_intelligence', module], True)

        return make_response("ok")

    @requires_permission('worker')
    @route('/<id>/get_file/<filehash>')
    def get_file(self, id, filehash):
        analysis = Analysis(get_or_404(current_user.analyses, _id=id))

        for file_type in analysis['generated_files']:
            for filepath in analysis['generated_files'][file_type]:
                filepath = filepath.encode('utf-8')
                if filehash == md5(filepath).hexdigest():
                    return file_download(filehash)

        filepath = analysis._file['filepath'].encode('utf-8')
        if filehash == md5(filepath).hexdigest():
            return file_download(analysis.get_main_file())

        return abort(404)

    def _save_analysis_file(self, id, path):
        file = request.files['file']
        analysis = Analysis(get_or_404(current_user.analyses, _id=id))
        dirpath = os.path.join(path, str(analysis['_id']))
        filepath = os.path.join(dirpath, secure_filename(file.filename))

        # Create parent dirs if they don't exist
        try:
            os.makedirs(dirpath)
        except:
            pass

        with open(filepath, "wb") as fd:
            copyfileobj(file.stream, fd)

        return filepath

    @requires_permission('worker')
    @route('/<id>/generated_file', methods=['POST'])
    def add_generated_file(self, id):
        filepath = self._save_analysis_file(id, os.path.join(fame_config.temp_path, 'generated_files'))

        return jsonify({'path': filepath})

    @requires_permission('worker')
    @route('/<id>/support_file/<module>', methods=['POST'])
    def add_support_file(self, id, module):
        filepath = self._save_analysis_file(id, os.path.join(fame_config.storage_path, 'support_files', module))

        return jsonify({'path': filepath})

    @route('/<id>/download/<module>/<filename>')
    def download_support_file(self, id, module, filename):
        """Download a support file.

        .. :quickref: Analysis; Download a support file.

        :param id: id of the analysis.
        :param module: name of the module.
        :param filename: name of the file to download.
        """
        analysis = get_or_404(current_user.analyses, _id=id)

        filepath = os.path.join(fame_config.storage_path, 'support_files', module, str(analysis['_id']), secure_filename(filename))
        if os.path.isfile(filepath):
            return file_download(filepath)
        else:
            # This code is here for compatibility
            # with older analyses
            filepath = os.path.join(fame_config.storage_path, 'support_files', str(analysis['_id']), secure_filename(filename))
            if os.path.isfile(filepath):
                return file_download(filepath)
            else:
                abort(404)
