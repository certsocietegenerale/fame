import os
import jinja2
from json import dumps
from bson import ObjectId
from datetime import datetime
from flask import Flask, redirect, request, url_for
from flask_login import LoginManager
from werkzeug import url_encode
from importlib import import_module

from fame.core import fame_init
from fame.core.user import User
from fame.common.config import fame_config
from fame.common.constants import AVATARS_ROOT
from web.views.files import FilesView
from web.views.analyses import AnalysesView
from web.views.modules import ModulesView
from web.views.search import SearchView
from web.views.configs import ConfigsView
from web.views.users import UsersView
from web.views.helpers import user_if_enabled

try:
    fame_init()
except:
    print "/!\\ Could not connect to MongoDB database."

app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
app.secret_key = fame_config.secret_key
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Set two tempalte folders (one is for modules)
template_loader = jinja2.ChoiceLoader([
    jinja2.FileSystemLoader('web/templates'),
    jinja2.FileSystemLoader('fame/modules'),
])
app.jinja_loader = template_loader


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = '/login'

auth_module = import_module('web.auth.{}.views'.format(fame_config.auth))
app.register_blueprint(auth_module.auth)


@login_manager.user_loader
def load_user(user_id):
    return user_if_enabled(User.get(_id=ObjectId(user_id)))


@login_manager.token_loader
def token_loader(token):
    return user_if_enabled(User.get(auth_token=token))


@login_manager.request_loader
def api_auth(request):
    api_key = request.headers.get('X-API-KEY')
    user = User.get(api_key=api_key)

    if user:
        user.is_api = True

    return user_if_enabled(user)


# Template Filters
@app.template_filter('date')
def filter_date(value, format='%Y-%m-%d %H:%M'):
    return value.strftime(format)


@app.template_filter()
def to_json(value):
    return dumps(value, indent=2)


@app.template_filter()
def smart_join(value, separator=", "):
    if value is None:
        return ''
    if isinstance(value, basestring):
        return value
    else:
        return separator.join(value)


@app.template_filter()
def form_value(value):
    if value is None:
        return ''
    else:
        return value


@app.template_filter()
def timesince(dt, default="just now"):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.
    """
    now = datetime.now()
    diff = now - dt

    periods = (
        (diff.days / 365, "year", "years"),
        (diff.days / 30, "month", "months"),
        (diff.days / 7, "week", "weeks"),
        (diff.days, "day", "days"),
        (diff.seconds / 3600, "hour", "hours"),
        (diff.seconds / 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),
    )

    for period, singular, plural in periods:
        if period:
            return "%d %s ago" % (period, singular if period == 1 else plural)

    return default


@app.template_filter()
def unique(l):
    return list(set(l))


@app.template_filter()
def avatar(user_id):
    if os.path.exists(os.path.join(AVATARS_ROOT, "{}.png".format(user_id))):
        return url_for('static', filename="img/avatars/{}.png".format(user_id))
    else:
        return url_for('static', filename="img/avatars/default.png")


@app.template_global()
def delete_query(*new_values):
    args = request.args.copy()

    for key in new_values:
        del args[key]

    return '{}?{}'.format(request.path, url_encode(args))


@app.template_global()
def modify_query(key, value):
    args = request.args.copy()
    args[key] = value

    return '{}?{}'.format(request.path, url_encode(args))


@app.route('/')
def root():
    return redirect('/analyses')


FilesView.register(app)
AnalysesView.register(app)
ModulesView.register(app)
SearchView.register(app)
ConfigsView.register(app)
UsersView.register(app)

if __name__ == '__main__':
    app.run(debug=True, port=4200, host="0.0.0.0")
