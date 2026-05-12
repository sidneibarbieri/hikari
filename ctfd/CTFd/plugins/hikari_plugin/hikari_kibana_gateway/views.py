from flask import redirect, request, url_for

from CTFd.plugins import bypass_csrf_protection
from CTFd.utils.decorators import authed_only

from .activity import record_kibana_activity
from .proxy import proxy_to_kibana


KIBANA_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")


def register(blueprint):
    blueprint.add_url_rule(
        "/hikari/siem",
        "siem_entrypoint",
        siem_entrypoint,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/hikari/kibana",
        "kibana_gateway_root",
        kibana_gateway,
        defaults={"proxy_path": ""},
        methods=KIBANA_METHODS,
    )
    blueprint.add_url_rule(
        "/hikari/kibana/<path:proxy_path>",
        "kibana_gateway",
        kibana_gateway,
        methods=KIBANA_METHODS,
    )


@authed_only
def siem_entrypoint():
    return redirect(url_for("hikariplugin.kibana_gateway", proxy_path="app/discover"))


@bypass_csrf_protection
@authed_only
def kibana_gateway(proxy_path: str):
    body = request.get_data(cache=True)
    response = proxy_to_kibana(proxy_path, body)
    record_kibana_activity(proxy_path, request.method, body, response.status_code)
    return response
