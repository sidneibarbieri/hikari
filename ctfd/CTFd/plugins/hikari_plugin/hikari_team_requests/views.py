"""Participant and captain views for approved team membership."""

from datetime import datetime

from flask import abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError

from CTFd.cache import clear_team_session, clear_user_session
from CTFd.models import Teams, Users, db
from CTFd.utils import get_config
from CTFd.utils.decorators import authed_only, registered_only
from CTFd.utils.decorators.modes import require_team_mode
from CTFd.utils.user import get_current_user

from .models import TeamMembershipRequest


def register(blueprint: object) -> None:
    """Attach team discovery and approval routes to the Hikari blueprint."""
    blueprint.add_url_rule(
        "/hikari/teams/join",
        endpoint="hikari_team_directory",
        view_func=directory,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/hikari/teams/<int:team_id>/request",
        endpoint="hikari_team_request",
        view_func=create_request,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/hikari/team/requests",
        endpoint="hikari_team_requests",
        view_func=review_requests,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/hikari/team/requests/<int:request_id>/approve",
        endpoint="hikari_team_request_approve",
        view_func=approve_request,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/hikari/team/requests/<int:request_id>/reject",
        endpoint="hikari_team_request_reject",
        view_func=reject_request,
        methods=["POST"],
    )


@authed_only
@registered_only
@require_team_mode
def directory():
    """List teams that can receive an approved membership request."""
    user = get_current_user()
    if user.team_id:
        return redirect(url_for("teams.private"))

    team_name = request.args.get("q", "").strip()
    query = Teams.query.filter_by(hidden=False, banned=False)
    if team_name:
        query = query.filter(Teams.name.like(f"%{team_name}%"))
    teams = query.order_by(Teams.name.asc()).all()
    pending_request = TeamMembershipRequest.query.filter_by(
        user_id=user.id,
        status="pending",
    ).first()
    return render_template(
        "hikari-team-directory.html",
        teams=teams,
        pending_request=pending_request,
        query=team_name,
        csrf_nonce=session.get("nonce"),
    )


@authed_only
@registered_only
@require_team_mode
def create_request(team_id: int):
    """Create one pending request for the authenticated participant."""
    user = get_current_user()
    if user.team_id:
        flash("Você já participa de uma equipe.", "danger")
        return redirect(url_for("teams.private"))
    if TeamMembershipRequest.query.filter_by(user_id=user.id, status="pending").first():
        flash("Você já possui uma solicitação de entrada pendente.", "danger")
        return redirect(url_for("hikariplugin.hikari_team_directory"))

    team = Teams.query.filter_by(id=team_id, hidden=False, banned=False).first_or_404()
    if _team_is_full(team):
        flash("A equipe já atingiu o limite de integrantes.", "danger")
        return redirect(url_for("hikariplugin.hikari_team_directory"))

    membership_request = TeamMembershipRequest.query.filter_by(
        team_id=team.id,
        user_id=user.id,
    ).first()
    if membership_request is None:
        membership_request = TeamMembershipRequest(team_id=team.id, user_id=user.id)
        db.session.add(membership_request)
    else:
        membership_request.status = "pending"
        membership_request.requested_at = datetime.utcnow()
        membership_request.resolved_at = None
        membership_request.resolved_by_user_id = None
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Esta solicitação já foi registrada.", "danger")
    else:
        flash(f"Solicitação enviada para a equipe {team.name}.", "success")
    return redirect(url_for("hikariplugin.hikari_team_directory"))


@authed_only
@registered_only
@require_team_mode
def review_requests():
    """Show pending requests to the captain of the current team."""
    team = _captained_team()
    requests = TeamMembershipRequest.query.filter_by(
        team_id=team.id,
        status="pending",
    ).order_by(TeamMembershipRequest.requested_at.asc()).all()
    return render_template(
        "hikari-team-requests.html",
        team=team,
        requests=requests,
        csrf_nonce=session.get("nonce"),
    )


@authed_only
@registered_only
@require_team_mode
def approve_request(request_id: int):
    """Approve a pending request and add its participant to the team."""
    team = _captained_team()
    membership_request = _pending_request_for_team(request_id, team.id)
    participant = Users.query.filter_by(id=membership_request.user_id).first_or_404()
    if participant.team_id:
        _resolve(membership_request, "rejected")
        flash("A solicitação foi encerrada porque a pessoa já entrou em outra equipe.", "danger")
        return redirect(url_for("hikariplugin.hikari_team_requests"))
    if _team_is_full(team):
        flash("A equipe já atingiu o limite de integrantes.", "danger")
        return redirect(url_for("hikariplugin.hikari_team_requests"))

    participant.team_id = team.id
    _resolve(membership_request, "approved")
    clear_user_session(user_id=participant.id)
    clear_team_session(team_id=team.id)
    flash(f"{participant.name} entrou na equipe.", "success")
    return redirect(url_for("hikariplugin.hikari_team_requests"))


@authed_only
@registered_only
@require_team_mode
def reject_request(request_id: int):
    """Reject a pending request without changing participant membership."""
    team = _captained_team()
    membership_request = _pending_request_for_team(request_id, team.id)
    _resolve(membership_request, "rejected")
    flash("Solicitação recusada.", "success")
    return redirect(url_for("hikariplugin.hikari_team_requests"))


def _captained_team() -> Teams:
    user = get_current_user()
    team = Teams.query.filter_by(id=user.team_id, captain_id=user.id).first()
    if team is None:
        abort(403, description="Apenas o capitão da equipe pode revisar solicitações.")
    return team


def _pending_request_for_team(request_id: int, team_id: int) -> TeamMembershipRequest:
    return TeamMembershipRequest.query.filter_by(
        id=request_id,
        team_id=team_id,
        status="pending",
    ).first_or_404()


def _team_is_full(team: Teams) -> bool:
    limit = int(get_config("team_size", default=0))
    return bool(limit and len(team.members) >= limit)


def _resolve(membership_request: TeamMembershipRequest, status: str) -> None:
    membership_request.status = status
    membership_request.resolved_at = datetime.utcnow()
    membership_request.resolved_by_user_id = get_current_user().id
    db.session.commit()
