"""Admin-only views for configuring and controlling an execution."""

from datetime import datetime

from flask import flash, redirect, render_template, request, session, url_for
from pydantic import ValidationError

from CTFd.models import db
from CTFd.utils.decorators import admins_only

from .dto import CompetitionDraft
from .models import CompetitionRun
from . import service
from .timezone import format_schedule_time, operator_time_zone, parse_local_schedule


def _now() -> datetime:
    return datetime.utcnow()


def _run_or_404(run_id: int) -> CompetitionRun:
    return CompetitionRun.query.filter_by(id=run_id).first_or_404()


@admins_only
def dashboard():
    if request.method == "POST":
        return _create_run()
    runs = CompetitionRun.query.order_by(CompetitionRun.id.desc()).all()
    return render_template(
        "hikari-competitions.html",
        runs=runs,
        active_run=service.active_run(),
        csrf_nonce=session.get("nonce"),
        format_schedule_time=format_schedule_time,
        operator_time_zone=operator_time_zone().key,
    )


def _create_run():
    try:
        draft = CompetitionDraft(
            key=request.form.get("key", ""),
            name=request.form.get("name", ""),
            scoring_mode=request.form.get("scoring_mode", ""),
            duration_minutes=request.form.get("duration_minutes", ""),
        )
    except ValidationError as error:
        flash(error.errors()[0]["msg"], "danger")
        return redirect(url_for("hikariplugin.hikari_competitions_dashboard"))

    if CompetitionRun.query.filter_by(key=draft.key).first() is not None:
        flash("Já existe uma execução com essa chave.", "danger")
        return redirect(url_for("hikariplugin.hikari_competitions_dashboard"))

    run = CompetitionRun(
        key=draft.key,
        name=draft.name.strip(),
        scoring_mode=draft.scoring_mode,
        duration_minutes=draft.duration_minutes,
    )
    db.session.add(run)
    db.session.commit()
    # Close play until the operator schedules or starts this execution.
    service.close_for_draft(run, _now())
    flash("Execução criada. Revise o modo de pontuação antes de iniciá-la.", "success")
    return redirect(url_for("hikariplugin.hikari_competitions_dashboard"))


@admins_only
def start(run_id: int):
    run = _run_or_404(run_id)
    try:
        service.start_run(run, _now())
    except ValueError as error:
        flash(str(error), "danger")
    else:
        flash("Execução iniciada e prazo aplicado ao CTFd.", "success")
    return redirect(url_for("hikariplugin.hikari_competitions_dashboard"))


@admins_only
def schedule(run_id: int):
    run = _run_or_404(run_id)
    raw_start = request.form.get("starts_at", "")
    try:
        starts_at = parse_local_schedule(raw_start)
        service.schedule_run(run, starts_at, _now())
    except ValueError as error:
        flash(str(error) or "Horário de início inválido", "danger")
    else:
        flash("Execução agendada. Cadastros permanecem disponíveis até o início.", "success")
    return redirect(url_for("hikariplugin.hikari_competitions_dashboard"))


@admins_only
def adjust(run_id: int):
    run = _run_or_404(run_id)
    try:
        service.adjust_run(run, int(request.form.get("adjust_minutes", "0")), _now())
    except (TypeError, ValueError) as error:
        flash(str(error) or "Ajuste de prazo inválido", "danger")
    else:
        flash("Prazo ajustado.", "success")
    return redirect(url_for("hikariplugin.hikari_competitions_dashboard"))


@admins_only
def pause(run_id: int):
    run = _run_or_404(run_id)
    try:
        service.pause_run(run, _now())
    except ValueError as error:
        flash(str(error), "danger")
    else:
        flash("Execução pausada. Submissões ficam bloqueadas até a retomada.", "success")
    return redirect(url_for("hikariplugin.hikari_competitions_dashboard"))


@admins_only
def resume(run_id: int):
    run = _run_or_404(run_id)
    try:
        service.resume_run(run, _now())
    except ValueError as error:
        flash(str(error), "danger")
    else:
        flash("Execução retomada com o tempo restante preservado.", "success")
    return redirect(url_for("hikariplugin.hikari_competitions_dashboard"))


@admins_only
def finish(run_id: int):
    run = _run_or_404(run_id)
    try:
        service.finish_run(run, _now())
    except ValueError as error:
        flash(str(error), "danger")
    else:
        flash("Execução encerrada. Faça o checkpoint antes de reutilizar a instalação.", "success")
    return redirect(url_for("hikariplugin.hikari_competitions_dashboard"))


@admins_only
def revert(run_id: int):
    run = _run_or_404(run_id)
    try:
        service.revert_to_draft(run, _now())
    except ValueError as error:
        flash(str(error), "danger")
    else:
        flash("Execução devolvida a rascunho. O jogo voltou a ficar fechado.", "success")
    return redirect(url_for("hikariplugin.hikari_competitions_dashboard"))


@admins_only
def cancel(run_id: int):
    run = _run_or_404(run_id)
    try:
        service.cancel_run(run, _now())
    except ValueError as error:
        flash(str(error), "danger")
    else:
        flash("Agendamento cancelado.", "success")
    return redirect(url_for("hikariplugin.hikari_competitions_dashboard"))
