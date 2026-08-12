"""State transitions for one CTFd competition execution."""

from datetime import datetime, timedelta

from CTFd.models import Submissions, db
from CTFd.utils import get_config, set_config

from .models import CompetitionRun


ACTIVE_STATUSES = {"scheduled", "running", "paused"}


def active_run() -> CompetitionRun | None:
    """Return the only execution currently controlling this deployment."""
    return (
        CompetitionRun.query.filter(CompetitionRun.status.in_(ACTIVE_STATUSES))
        .order_by(CompetitionRun.id.desc())
        .first()
    )


def schedule_run(run: CompetitionRun, starts_at: datetime, now: datetime) -> None:
    """Schedule a draft execution while keeping registration available."""
    other = active_run()
    if other is not None and other.id != run.id:
        raise ValueError("Já existe uma execução controlando esta instalação")
    if run.status != "draft":
        raise ValueError("Apenas execuções em rascunho podem ser agendadas")
    if starts_at <= now:
        raise ValueError("Escolha um horário futuro para o início")
    _validate_scoring_mode(run)

    run.starts_at = starts_at
    run.ends_at = starts_at + timedelta(minutes=run.duration_minutes)
    run.status = "scheduled"
    _apply_schedule(run, paused=False)
    db.session.commit()


def start_run(run: CompetitionRun, now: datetime) -> None:
    """Start a draft or scheduled execution immediately."""
    other = active_run()
    if other is not None and other.id != run.id:
        raise ValueError("Já existe uma execução ativa nesta instalação")
    if run.status not in {"draft", "scheduled"}:
        raise ValueError("A execução não pode ser iniciada no estado atual")
    _validate_scoring_mode(run)

    run.starts_at = now
    run.ends_at = now + timedelta(minutes=run.duration_minutes)
    run.status = "running"
    _apply_schedule(run, paused=False)
    _activate_initial_logs()
    db.session.commit()


def synchronize_active_run(now: datetime) -> CompetitionRun | None:
    """Apply scheduled start and end transitions when the application receives traffic."""
    run = active_run()
    if run is None:
        return None
    if run.status == "scheduled" and run.starts_at is not None and run.starts_at <= now:
        run.status = "running"
        _activate_initial_logs()
        db.session.commit()
        return run
    if run.status == "running" and run.ends_at is not None and run.ends_at <= now:
        run.status = "finished"
        db.session.commit()
    return run


def extend_run(run: CompetitionRun, additional_minutes: int, now: datetime) -> None:
    """Extend a running execution without changing its start time."""
    if run.status != "running" or run.ends_at is None:
        raise ValueError("Apenas uma execução em andamento pode receber tempo adicional")
    if not 5 <= additional_minutes <= 480 or additional_minutes % 5:
        raise ValueError("Informe de 5 a 480 minutos, em múltiplos de cinco")

    base = max(run.ends_at, now)
    run.ends_at = base + timedelta(minutes=additional_minutes)
    _apply_schedule(run, paused=False)
    db.session.commit()


def pause_run(run: CompetitionRun, now: datetime) -> None:
    """Pause a run and preserve its remaining active time."""
    if run.status != "running" or run.ends_at is None:
        raise ValueError("A execução não está em andamento")
    remaining = int((run.ends_at - now).total_seconds())
    if remaining <= 0:
        raise ValueError("O prazo da execução já terminou")

    run.paused_remaining_seconds = remaining
    run.status = "paused"
    set_config("paused", True)
    db.session.commit()


def resume_run(run: CompetitionRun, now: datetime) -> None:
    """Resume a paused execution using the active time saved on pause."""
    if run.status != "paused":
        raise ValueError("A execução não está pausada")
    if run.paused_remaining_seconds is None or run.paused_remaining_seconds <= 0:
        raise ValueError("A execução pausada não tem tempo restante válido")

    run.ends_at = now + timedelta(seconds=run.paused_remaining_seconds)
    run.paused_remaining_seconds = None
    run.status = "running"
    _apply_schedule(run, paused=False)
    db.session.commit()


def finish_run(run: CompetitionRun, now: datetime) -> None:
    """End an execution and prevent further participant submissions."""
    if run.status not in ACTIVE_STATUSES:
        raise ValueError("A execução já foi encerrada")

    run.ends_at = now
    run.paused_remaining_seconds = None
    run.status = "finished"
    _apply_schedule(run, paused=False)
    db.session.commit()


def cancel_run(run: CompetitionRun) -> None:
    """Cancel a scheduled execution without creating an invalid time window."""
    if run.status != "scheduled":
        raise ValueError("Apenas uma execução agendada pode ser cancelada")

    run.status = "cancelled"
    set_config("start", 0)
    set_config("end", 0)
    set_config("paused", False)
    set_config("hikari_competition_key", "")
    db.session.commit()


def _apply_schedule(run: CompetitionRun, paused: bool) -> None:
    """Synchronize the active run with CTFd's global schedule settings."""
    if run.starts_at is None or run.ends_at is None:
        raise ValueError("A execução precisa ter início e término definidos")
    set_config("ctf_name", run.name)
    set_config("user_mode", run.scoring_mode)
    set_config("start", int(run.starts_at.timestamp()))
    set_config("end", int(run.ends_at.timestamp()))
    set_config("paused", paused)
    set_config("hikari_competition_key", run.key)


def _validate_scoring_mode(run: CompetitionRun) -> None:
    """Prevent changing the score owner after participant data exists."""
    configured_mode = get_config("user_mode")
    if configured_mode == run.scoring_mode:
        return
    if Submissions.query.count() > 0:
        raise ValueError(
            "A modalidade não pode mudar nesta instalação porque já há submissões. "
            "Use uma instalação isolada para a nova execução."
        )


def _activate_initial_logs() -> None:
    """Release log sets belonging to visible challenges without prerequisites."""
    from CTFd.plugins.hikari_challenge import HikariController
    from CTFd.plugins.hikari_plugin import hikari_models

    challenges = hikari_models.HikariChallengeModel.query.all()
    for challenge in challenges:
        requirements = challenge.requirements or {}
        if requirements.get("prerequisites") or challenge.logs_activated:
            continue
        if challenge.state == "visible":
            HikariController.activate_logs(challenge.id)
            challenge.logs_activated = True
