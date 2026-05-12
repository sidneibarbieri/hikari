import json
import os

from flask import Response, flash, redirect, render_template, request, stream_with_context, url_for
from pydantic import ValidationError

from CTFd.models import db
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.utils.user import get_current_user, get_ip

from .dto import FeedbackPayload
from .forms import FeedbackForm
from .models import FeedbackResponse


def register(blueprint):
    blueprint.add_url_rule("/hikari/feedback", "feedback", feedback, methods=["GET", "POST"])
    blueprint.add_url_rule(
        "/admin/hikari/research/feedback.jsonl",
        "feedback_export_jsonl",
        feedback_export_jsonl,
        methods=["GET"],
    )


@authed_only
def feedback():
    form = FeedbackForm()
    if request.method == "POST" and form.validate_on_submit():
        payload = payload_from_form(form)
        user = get_current_user()
        response = FeedbackResponse(
            user_id=user.id,
            team_id=user.team_id,
            competition_key=current_competition_key(),
            payload=payload.json(),
            request_ip=get_ip(),
            user_agent=request.headers.get("User-Agent"),
        )
        db.session.add(response)
        db.session.commit()
        flash("Feedback submitted.", "success")
        return redirect(url_for("hikariplugin.feedback"))

    return render_template("hikari-feedback.html", form=form)


@admins_only
def feedback_export_jsonl():
    return Response(
        stream_with_context(feedback_jsonl_lines()),
        mimetype="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=hikari-feedback.jsonl"},
    )


def payload_from_form(form):
    try:
        return FeedbackPayload(
            phase=form.phase.data,
            experience_level=form.experience_level.data,
            prior_ctf=bool(form.prior_ctf.data),
            blue_team_familiarity=form.blue_team_familiarity.data,
            interface_rating=form.interface_rating.data,
            challenge_difficulty=form.challenge_difficulty.data,
            dashboard_relevance=form.dashboard_relevance.data,
            useful_dashboard_elements=form.useful_dashboard_elements.data or "",
            unused_dashboard_elements=form.unused_dashboard_elements.data or "",
            technical_issues=bool(form.technical_issues.data),
            technical_issue_notes=form.technical_issue_notes.data,
            learning_effectiveness=form.learning_effectiveness.data,
            learned_areas=form.learned_areas.data,
            operational_confidence_before=form.operational_confidence_before.data,
            operational_confidence_after=form.operational_confidence_after.data,
            realism=form.realism.data,
            methodology_notes=form.methodology_notes.data,
            suggested_improvements=form.suggested_improvements.data,
        )
    except ValidationError as error:
        raise ValueError(str(error)) from error


def feedback_jsonl_lines():
    query = FeedbackResponse.query.order_by(FeedbackResponse.submitted_at.asc())
    for record in query.yield_per(100):
        yield json.dumps(record_to_dict(record), sort_keys=True) + "\n"


def record_to_dict(record):
    return {
        "id": record.id,
        "user_id": record.user_id,
        "team_id": record.team_id,
        "competition_key": record.competition_key,
        "submitted_at": record.submitted_at.isoformat(),
        "payload": json.loads(record.payload),
        "request_ip": record.request_ip,
        "user_agent": record.user_agent,
    }


def current_competition_key():
    return os.environ.get("HIKARI_COMPETITION_KEY", "local")
