from flask import abort, render_template, request, url_for

from CTFd.plugins import bypass_csrf_protection
from CTFd.utils.decorators import authed_only
from CTFd.utils.dates import ctftime
from CTFd.utils.user import is_admin

from .activity import record_kibana_activity
from .proxy import proxy_to_kibana
from .summary import build_siem_summary


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
    _require_active_hunting_window()
    return render_template(
        "hikari-siem.html",
        summary=build_siem_summary(),
        dashboard_url=(
            url_for("hikariplugin.kibana_gateway", proxy_path="app/dashboards")
            + "#/view/hikari-siem"
        ),
        discover_url=url_for("hikariplugin.kibana_gateway", proxy_path="app/discover"),
    )


@bypass_csrf_protection
@authed_only
def kibana_gateway(proxy_path: str):
    _require_active_hunting_window()
    body = request.get_data(cache=True)
    response = proxy_to_kibana(proxy_path, body)
    record_kibana_activity(proxy_path, request.method, body, response.status_code)
    return response


def _require_active_hunting_window() -> None:
    """Keep competition telemetry unavailable until its configured time window."""
    if not ctftime() and not is_admin():
        abort(403, description="A investigação no SIEM estará disponível durante a competição.")
