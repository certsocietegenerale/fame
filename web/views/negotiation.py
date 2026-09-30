import re
from urllib.parse import unquote, urlparse, urlsplit
from flask import redirect as flask_redirect
from flask import request, get_flashed_messages, render_template
from flask.wrappers import Response
from bson.json_util import dumps
from fame.common.config import fame_config


def should_render_as_html():
    best_accept = request.accept_mimetypes.best_match(["text/html", "application/json"])
    api_key = bool(request.headers.get("X-API-KEY"))
    token = bool(request.headers.get("Authorization")) and request.headers.get(
        "Authorization"
    ).lower().startswith("bearer ")

    return best_accept == "text/html" and not api_key and not token


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


def is_allowed_domain(target):
    if not target or not isinstance(target, str):
        return False

    if any(char.isspace() or ord(char) < 32 for char in target):
        return False

    normalized_target = target.replace("\\", "/")
    decoded_target = unquote(normalized_target)
    if decoded_target.startswith("//"):
        return False

    if re.search(r"%(?:25)*(?:2f|5c|0[0-9a-f])", target, re.IGNORECASE):
        return False

    try:
        parsed = urlsplit(normalized_target)
    except ValueError:
        return False

    if any(ord(char) < 32 for char in decoded_target):
        return False

    if parsed.scheme and not parsed.netloc:
        return False

    if not parsed.scheme and not parsed.netloc:
        return normalized_target.startswith("/")

    allowed_origins = set()
    for url in (fame_config.get("fame_url") or "").split():
        try:
            parsed_url = urlparse(url)
        except ValueError:
            continue
        if parsed_url.scheme and parsed_url.netloc:
            allowed_origins.add((parsed_url.scheme.lower(), parsed_url.netloc.lower()))

    return (
        not parsed.username
        and not parsed.password
        and (parsed.scheme.lower(), parsed.netloc.lower()) in allowed_origins
    )


def safe_redirect_target(target, fallback="/"):
    if is_allowed_domain(target):
        return target.replace("\\", "/")
    return fallback


def redirect(data, path):
    if should_render_as_html():
        return flask_redirect(safe_redirect_target(path))

    return render_json(data)


def validation_error(path=None):
    if should_render_as_html():
        return flask_redirect(safe_redirect_target(path))

    return render_json({"errors": get_flashed_messages()})
