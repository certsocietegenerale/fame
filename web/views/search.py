from flask import request
from flask_login import current_user
from flask_classful import FlaskView

from web.views.mixins import UIView
from web.views.helpers import clean_files, clean_analyses
from web.views.negotiation import render


class SearchView(FlaskView, UIView):
    def post(self):
        query = request.form['query']

        files = []
        for file in current_user.files.find({'$text': {'$search': query}}):
            files.append(file)

        analyses = []
        for analysis in current_user.analyses.find({'$text': {'$search': query}}):
            file = current_user.files.find_one({'_id': analysis['file']})
            analysis['file'] = clean_files(file)
            analyses.append(analysis)

        results = {'files': clean_files(files), 'analyses': clean_analyses(analyses)}

        return render(results, 'search.html')
