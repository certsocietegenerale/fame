from flask import redirect as flask_redirect
from flask import request, get_flashed_messages, render_template
from flask.wrappers import Response
from bson.json_util import dumps


def should_render_as_html():
    best = request.accept_mimetypes.best_match(["text/html", "application/json"])

    return best == "text/html"


def render_json(data):
    body = dumps(data)

    return Response(response=body, mimetype="application/json")


def render_html(data, template, ctx=None):
    ctx = ctx or {"data": data}

    return render_template(template, **ctx)


def render(data, template, ctx=None):
    if should_render_as_html():
        return render_html(data, template, ctx)
    else:
        return render_json(data)


def redirect(data, path):
    if should_render_as_html():
        return flask_redirect(path)

    return render_json(data)


def validation_error(path=None):
    if should_render_as_html():
        if path:
            return flask_redirect(path)

        return flask_redirect(request.referrer)

    return render_json({"errors": get_flashed_messages()})
