"""Flask handlers for the research surface.

Two read-only endpoints behind admin auth:
  /admin/hikari/research                   HTML dashboard
  /admin/hikari/research/export.jsonl      streamed activity log export
"""

from typing import Optional

from flask import Response, render_template, request, stream_with_context
from werkzeug.exceptions import BadRequest

from CTFd.utils.decorators import admins_only
from CTFd.plugins.hikari_plugin.hikari_competitions.context import current_competition_key

from . import exporter, queries
from .dto import ResearchFilters, ResearchSummary


def _optional_int(value: str, field_name: str) -> Optional[int]:
    if value == "":
        return None
    if not value.isdecimal():
        raise BadRequest(f"{field_name} deve ser inteiro")
    return int(value)


def _filters_from_request() -> ResearchFilters:
    requested_key = request.args.get("competition_key")
    competition_key = (
        requested_key.strip() if requested_key is not None else current_competition_key()
    )
    if not competition_key:
        competition_key = current_competition_key()
    event_type = request.args.get("event_type", "").strip() or None
    actor_id = _optional_int(request.args.get("actor_id", "").strip(), "actor_id")
    team_id = _optional_int(request.args.get("team_id", "").strip(), "team_id")
    return ResearchFilters(
        competition_key=competition_key,
        event_type=event_type,
        actor_id=actor_id,
        team_id=team_id,
    )


@admins_only
def dashboard():
    filters = _filters_from_request()
    summary = ResearchSummary(
        filters=filters,
        total_events=queries.total_events(filters),
        events_by_type=queries.event_counts_by_type(filters),
        teams_by_event_count=queries.event_counts_by_team(filters),
        submission_patterns=queries.submission_patterns(filters.competition_key),
        team_postures=queries.team_submission_posture(filters.competition_key),
        hunting_depth=queries.hunting_depth_by_actor(
            competition_key=filters.competition_key
        ),
        feedback=queries.feedback_summary(filters.competition_key),
        available_competition_keys=queries.available_competition_keys(),
        available_event_types=queries.available_event_types(filters.competition_key),
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
