from flask import redirect as flask_redirect
from flask import request, get_flashed_messages
from flask_negotiation import Render
from flask_negotiation.renderers import template_renderer, renderer
from flask_negotiation.media_type import MediaType, acceptable_media_types, choose_media_type
from bson.json_util import dumps

html = MediaType('text/html')


def redirect(data, path):
    if choose_media_type(acceptable_media_types(request), [html]):
        return flask_redirect(path)
    else:
        return render_json(data)


def validation_error(path=None):
    if choose_media_type(acceptable_media_types(request), [html]):
        if path:
            return flask_redirect(path)
        else:
            return flask_redirect(request.referrer)
    else:
        return render_json({'errors': get_flashed_messages()})


@renderer('application/json')
def bson_renderer(data, template=None, ctx=None):
    return dumps(data)


render = Render(renderers=[template_renderer, bson_renderer])
render_json = Render(renderers=[bson_renderer])
