"""Flask handlers for the research surface.

Two read-only endpoints behind admin auth:
  /admin/hikari/research                   HTML dashboard
  /admin/hikari/research/export.jsonl      streamed activity log export
"""

from flask import Response, render_template, request, stream_with_context
from werkzeug.exceptions import BadRequest

from CTFd.utils.decorators import admins_only

from . import exporter, queries
from .dto import ResearchFilters, ResearchSummary


def _optional_int(value: str, field_name: str):
    if value == "":
        return None
    if not value.isdecimal():
        raise BadRequest(f"{field_name} deve ser inteiro")
    return int(value)


def _filters_from_request() -> ResearchFilters:
    event_type = request.args.get("event_type", "").strip() or None
    actor_id = _optional_int(request.args.get("actor_id", "").strip(), "actor_id")
    team_id = _optional_int(request.args.get("team_id", "").strip(), "team_id")
    return ResearchFilters(event_type=event_type, actor_id=actor_id, team_id=team_id)


@admins_only
def dashboard():
    filters = _filters_from_request()
    summary = ResearchSummary(
        filters=filters,
        total_events=queries.total_events(filters),
        events_by_type=queries.event_counts_by_type(filters),
        teams_by_event_count=queries.event_counts_by_team(filters),
        available_event_types=queries.available_event_types(),
        recent=queries.recent_events(filters),
    )
    return render_template("hikari-research.html", summary=summary)


@admins_only
def export_jsonl():
    # stream_with_context keeps the Flask app/request context alive while the
    # generator yields, so the SQLAlchemy session stays usable after the view
    # function returns control to the WSGI server.
    return Response(
        stream_with_context(exporter.jsonl_lines(_filters_from_request())),
        mimetype="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=hikari-activity.jsonl"},
    )
