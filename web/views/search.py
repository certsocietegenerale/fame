from flask import request
from flask_login import current_user
from flask_classful import FlaskView
from fame.core.store import store

from web.views.mixins import UIView
from web.views.helpers import clean_files, clean_analyses, clean_users
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
        for analysis in analyses:
            if 'analyst' in analysis:
                analyst = store.users.find_one({'_id': analysis['analyst']})
                analysis['analyst'] = clean_users(analyst)

            if 'reviewed' in analysis and analysis['reviewed']:
                reviewer = store.users.find_one({'_id': analysis['reviewed']})
                analysis['reviewed'] = clean_users(reviewer)

        for file in files:
            if 'reviewed' in file and file['reviewed']:
                reviewer = store.users.find_one({'_id': file['reviewed']})
                file['reviewed'] = clean_users(reviewer)

        return render(results, 'search.html')
