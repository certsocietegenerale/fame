from pymongo import DESCENDING
from flask import current_app, g
from flask_login import current_user

from fame.core.store import store
from web.views.helpers import csrf_protect


class AuthenticatedView(object):
    def before_request(self, *args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()

        if not current_user.is_api:
            csrf_protect()


class UIView(AuthenticatedView):
    def before_request(self, *args, **kwargs):
        redir = AuthenticatedView.before_request(self, *args, **kwargs)
        if redir:
            return redir

        g.last_analyses = []
        analyses = current_user.analyses.find().sort('_id', DESCENDING).limit(4)

        for analysis in analyses:
            file = store.files.find_one({'_id': analysis['file']})
            analysis['file'] = file
            g.last_analyses.append(analysis)
