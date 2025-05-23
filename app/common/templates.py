import time
from typing import Any, Dict

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from app.auth.utils import AUTH_COOKIE, optional_current_user
from app.common import utils
from app.settings import settings


def app_context(request: Request) -> Dict[str, Any]:
    active_route = request.scope["route"].name if request.scope.get("route") else None

    user = None
    with utils.sync_await() as await_:
        try:
            session_token = await_(AUTH_COOKIE(request))
            if session_token:
                user = await_(optional_current_user(session_token))
        except Exception:
            pass

    return {
        # Used on all pages
        "request": request,
        "user": user,
        "settings": settings,
        "active_route_name": active_route,
    }


templates = Jinja2Templates(
    directory="app", context_processors=[app_context], auto_reload=True
)


def jinja_global_function(func):
    templates.env.globals[func.__name__] = func
    return func


@jinja_global_function
@pass_context
def static_url(context: dict, path: str) -> str:
    params = {"v": settings.VERSION}

    if not settings.is_prod:
        params["t"] = str(time.time())

    return (
        context["request"].url_for("static", path=path).include_query_params(**params)
    )


@jinja_global_function
@pass_context
def get_flashed_messages(context: dict) -> list:
    return utils.get_flashed_messages(context["request"])
