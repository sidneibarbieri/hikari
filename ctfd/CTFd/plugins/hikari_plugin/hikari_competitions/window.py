"""What the competition schedule looks like to whoever is watching.

Competitors asked, during the rehearsal, what time the competition would end.
The live board counted down and nothing else said anything, so the answer
existed only in the operator's head. This module turns the execution under way
into one description that every surface renders the same way.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .models import CompetitionRun
from .timezone import format_schedule_time


ROTULOS_DE_ESTADO = {
    "scheduled": "Ainda não começou",
    "running": "Em andamento",
    "paused": "Pausada",
    "finished": "Encerrada",
}


class CompetitionWindow(BaseModel):
    """The schedule of one execution, ready to be shown to a competitor."""

    name: str
    status: str
    status_label: str
    starts_at_label: Optional[str] = None
    ends_at_label: Optional[str] = None
    duration_minutes: int
    seconds_remaining: Optional[int] = None


def current_window(now: Optional[datetime] = None) -> Optional[CompetitionWindow]:
    """Describe the execution that governs this deployment, if there is one."""
    run = _run_on_display()
    if run is None:
        return None

    return CompetitionWindow(
        name=run.name,
        status=run.status,
        status_label=ROTULOS_DE_ESTADO.get(run.status, run.status),
        starts_at_label=format_schedule_time(run.starts_at),
        ends_at_label=format_schedule_time(run.ends_at),
        duration_minutes=_duration_minutes(run),
        seconds_remaining=_seconds_remaining(run, now or datetime.utcnow()),
    )


def _duration_minutes(run: CompetitionRun) -> int:
    """How long the execution lasts, measured on the window that is displayed.

    An execution ended early, or one whose deadline was adjusted, keeps the
    duration it was configured with. Showing that number next to a start and an
    end that disagree with it invites the reader to distrust all three, so the
    window itself is the source whenever it is complete.
    """
    if run.starts_at is None or run.ends_at is None:
        return run.duration_minutes
    return max(int((run.ends_at - run.starts_at).total_seconds() // 60), 0)


def _run_on_display() -> Optional[CompetitionRun]:
    """Return the execution people are looking at.

    An active execution always wins. Once it ends, the board keeps showing it
    rather than falling silent, because the audience still wants to read when
    the competition ran.
    """
    active = (
        CompetitionRun.query.filter(CompetitionRun.status.in_(("scheduled", "running", "paused")))
        .order_by(CompetitionRun.id.desc())
        .first()
    )
    if active is not None:
        return active
    return (
        CompetitionRun.query.filter(CompetitionRun.status == "finished")
        .order_by(CompetitionRun.ends_at.desc())
        .first()
    )


def _seconds_remaining(run: CompetitionRun, now: datetime) -> Optional[int]:
    """Seconds left on the clock, counted only while the clock is running."""
    if run.status == "paused":
        return run.paused_remaining_seconds
    if run.status != "running" or run.ends_at is None:
        return None
    remaining = int((run.ends_at - now).total_seconds())
    return max(remaining, 0)
