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


# A draft has no start time yet, so the platform is closed with a window that
# has not begun. CTFd treats an empty schedule as "no restriction", which would
# leave challenges and the SIEM open during the registration window.
DRAFT_CLOSED_DAYS = 365


def close_for_draft(run: CompetitionRun, now: datetime) -> None:
    """Keep play closed while an execution is only a draft.

    Registration and team formation stay available; challenges, submissions
    and the SIEM open when the operator schedules or starts the run, which
    overwrites this placeholder window.
    """
    if active_run() is not None:
        return
    placeholder_start = now + timedelta(days=DRAFT_CLOSED_DAYS)
    set_config("ctf_name", run.name)
    set_config("start", int(placeholder_start.timestamp()))
    set_config("end", int((placeholder_start + timedelta(minutes=run.duration_minutes)).timestamp()))
    set_config("paused", False)
    set_config("hikari_competition_key", run.key)
    db.session.commit()


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
        # Every other transition writes CTFd's global window through
        # _apply_schedule. The automatic promotion has to write it too, or the
        # platform would open with whatever window the previous run left behind.
        _apply_schedule(run, paused=False)
        _activate_initial_logs()
        db.session.commit()
        return run
    if run.status == "running" and run.ends_at is not None and run.ends_at <= now:
        run.status = "finished"
        db.session.commit()
    return run


# A shortened run still has to leave people time to finish what they are
# doing, so the new deadline can never land on top of the present moment.
MINIMUM_REMAINING_MINUTES = 5


def adjust_run(run: CompetitionRun, minutes: int, now: datetime) -> None:
    """Move the deadline of a running execution forward or backward."""
    if run.status != "running" or run.ends_at is None:
        raise ValueError("Apenas uma execução em andamento pode ter o prazo ajustado")
    if run.ends_at <= now:
        raise ValueError("O prazo da execução já terminou. Inicie uma nova execução.")
    if minutes == 0 or abs(minutes) > 480 or minutes % 5:
        raise ValueError("Informe de -480 a 480 minutos, em múltiplos de cinco")

    adjusted = run.ends_at + timedelta(minutes=minutes)
    if adjusted < now + timedelta(minutes=MINIMUM_REMAINING_MINUTES):
        raise ValueError(
            f"O novo prazo precisa deixar ao menos {MINIMUM_REMAINING_MINUTES} minutos. "
            "Para terminar agora, use Encerrar."
        )

    run.ends_at = adjusted
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


def change_duration(run: CompetitionRun, total_minutes: int, now: datetime) -> None:
    """Set how long an execution will last, before anyone starts playing.

    A running execution moves its deadline with adjust_run, which preserves the
    time already played. Before the start there is nothing to preserve, so the
    duration is simply what the operator now says it is, and a scheduled run
    keeps its start while its end moves.
    """
    if run.status not in {"draft", "scheduled"}:
        raise ValueError(
            "A duração só pode ser alterada antes do início. "
            "Com a execução em andamento, use Ajustar prazo"
        )

    run.duration_minutes = total_minutes
    if run.status == "scheduled" and run.starts_at is not None:
        run.ends_at = run.starts_at + timedelta(minutes=total_minutes)
        _apply_schedule(run, paused=False)
        db.session.commit()
        return

    db.session.commit()
    close_for_draft(run, now)


def revert_to_draft(run: CompetitionRun, now: datetime) -> None:
    """Undo an execution opened by mistake, while nobody has scored yet.

    Every other transition moves forward, so an operator who starts the wrong
    execution minutes before the real one has no way back. Once a submission
    exists the execution is history and reverting would erase it, so from that
    point the way out is to finish it.

    Logs already released into the SIEM stay there. They belong to the same
    challenges and the SIEM is closed again while the execution is a draft, so
    the real start finds them in place instead of injecting duplicates.
    """
    if run.status not in ACTIVE_STATUSES:
        raise ValueError(
            "Apenas uma execução agendada, em andamento ou pausada pode voltar a rascunho"
        )

    scored = _submissions_since(run.starts_at)
    if scored:
        raise ValueError(
            f"Esta execução já registrou {scored} submissão(ões). "
            "Use Encerrar para preservar o resultado."
        )

    run.status = "draft"
    run.starts_at = None
    run.ends_at = None
    run.paused_remaining_seconds = None
    db.session.commit()
    # Only after the status is persisted does this stop being the active run,
    # which is what lets close_for_draft shut the play window again.
    close_for_draft(run, now)


def _submissions_since(moment: datetime | None) -> int:
    """Count submissions recorded from a moment onwards."""
    if moment is None:
        return 0
    return Submissions.query.filter(Submissions.date >= moment).count()


def cancel_run(run: CompetitionRun, now: datetime) -> None:
    """Cancel a scheduled execution while keeping play surfaces closed."""
    if run.status != "scheduled":
        raise ValueError("Apenas uma execução agendada pode ser cancelada")

    run.status = "cancelled"
    close_for_draft(run, now)


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
    from CTFd.plugins.hikari_challenge.hikari_waves import liberar_ondas_iniciais

    liberar_ondas_iniciais(HikariController.activate_logs)
