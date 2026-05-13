import json
import os

from flask import Response, flash, redirect, render_template, request, stream_with_context, url_for
from pydantic import ValidationError

from CTFd.models import db
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.utils.user import get_current_user, get_ip

from .dto import FeedbackPayload
from .forms import FeedbackForm, iter_groups
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

    return render_template(
        "hikari-feedback.html",
        form=form,
        sections=list(iter_groups(form)),
    )


@admins_only
def feedback_export_jsonl():
    return Response(
        stream_with_context(feedback_jsonl_lines()),
        mimetype="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=hikari-feedback.jsonl"},
    )


_DTO_FIELDS = (
    "phase",
    "years_cyber_experience",
    "primary_role",
    "prior_ctf_count",
    "years_soc_experience",
    "formal_education",
    "self_cyber_defense_analyst",
    "self_incident_responder",
    "self_threat_warning_analyst",
    "self_forensics_analyst",
    "self_vuln_assessment_analyst",
    "tool_kibana",
    "tool_kql",
    "tool_attack_framework",
    "tool_other_siem",
    "mitre_tactics_practised",
    "tlx_mental_demand",
    "tlx_temporal_demand",
    "tlx_performance",
    "tlx_effort",
    "tlx_frustration",
    "sus_would_use_frequently",
    "sus_unnecessarily_complex",
    "sus_easy_to_use",
    "sus_needed_support",
    "sus_functions_well_integrated",
    "sus_too_much_inconsistency",
    "sus_quick_to_learn",
    "sus_cumbersome",
    "sus_felt_confident",
    "sus_needed_to_learn_a_lot",
    "learning_log_analysis",
    "learning_pattern_correlation",
    "learning_hypothesis_generation",
    "learning_tool_fluency",
    "learning_time_to_detect",
    "learning_documentation",
    "realism_attack_chain",
    "realism_telemetry",
    "realism_pace",
    "methodology_coherence",
    "nps_recommend",
    "most_valuable_technique",
    "biggest_learning_blocker",
    "suggested_scenarios",
    "other_comments",
)


def payload_from_form(form):
    """Build the Pydantic payload from the WTForm, coercing empty strings to None."""
    raw = {name: _normalise(getattr(form, name).data) for name in _DTO_FIELDS}
    try:
        return FeedbackPayload(**raw)
    except ValidationError as error:
        raise ValueError(str(error)) from error


def _normalise(value):
    if value == "" or value == []:
        return None if value == "" else []
    return value


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
