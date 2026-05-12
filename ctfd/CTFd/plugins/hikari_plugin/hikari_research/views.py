"""Flask handlers for the research surface.

Two read-only endpoints behind admin auth:
  /admin/hikari/research                   HTML dashboard
  /admin/hikari/research/export.jsonl      streamed activity log export
"""

from flask import Response, render_template, stream_with_context

from CTFd.utils.decorators import admins_only

from . import exporter, queries
from .dto import ResearchSummary


@admins_only
def dashboard():
    summary = ResearchSummary(
        total_events=queries.total_events(),
        events_by_type=queries.event_counts_by_type(),
        teams_by_event_count=queries.event_counts_by_team(),
        recent=queries.recent_events(),
    )
    return render_template("hikari-research.html", summary=summary)


@admins_only
def export_jsonl():
    # stream_with_context keeps the Flask app/request context alive while the
    # generator yields, so the SQLAlchemy session stays usable after the view
    # function returns control to the WSGI server.
    return Response(
        stream_with_context(exporter.jsonl_lines()),
        mimetype="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=hikari-activity.jsonl"},
    )
