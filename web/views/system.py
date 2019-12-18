from flask import flash, url_for
from flask_classy import FlaskView, route

from fame.core.analysis import Analysis
from fame.core.store import store
from web.views.helpers import get_or_404, requires_permission
from web.views.mixins import UIView
from web.views.negotiation import redirect, render


class SystemView(FlaskView, UIView):
    @requires_permission('system')
    def index(self):
        pending_analyses = []
        stale_analyses = []

        for analysis in store.analysis.find({'status': 'pending'}):
            file = store.files.find_one({'_id': analysis['file']})
            analysis['file'] = file
            pending_analyses.append(analysis)

        for analysis in store.analysis.find({'status': 'running', 'waiting_modules': {'$ne': []}}):
            file = store.files.find_one({'_id': analysis['file']})
            analysis['file'] = file
            stale_analyses.append(analysis)

        return render({'pending_analyses': pending_analyses, 'stale_analyses': stale_analyses}, "system/index.html")

    @route("/<id>/resume", methods=["POST"])
    def resume(self, id):
        analysis = Analysis(get_or_404(Analysis.get_collection(), _id=id))
        analysis.resume()

        flash("Resumed analysis {}".format(analysis['_id']))
        return redirect({}, url_for('SystemView:index'))
