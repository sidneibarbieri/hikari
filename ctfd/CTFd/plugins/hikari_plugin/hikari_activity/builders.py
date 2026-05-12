"""Build ActivityRecord instances from a live Flask request/response pair.

Each builder is a pure function that reads from the request/response and
returns a record. Building is separated from persisting so the listener can
choose to publish only, persist only, or both, without touching this module.
"""

from datetime import datetime, timezone
from typing import Optional

from flask import Request, Response

from .dto import ActivityRecord
from .event_map import ObservedEvent


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _actor_role(user_type: Optional[str]) -> Optional[str]:
    if user_type is None:
        return None
    if user_type == "admin":
        return "admin"
    return "user"


def _challenge_id_from_view_args(request: Request) -> Optional[int]:
    if not request.view_args:
        return None
    raw = request.view_args.get("challenge_id")
    if raw is None:
        return None
    return int(raw)


def build_record(
    event: ObservedEvent,
    request: Request,
    response: Response,
    actor_id: Optional[int],
    user_type: Optional[str],
    user_team_id: Optional[int],
) -> ActivityRecord:
    """Assemble an ActivityRecord from the request/response and actor state.

    All actor information is supplied by the caller. The builder stays pure
    and is straightforward to exercise in unit tests without a live session.
    """
    target_kind: Optional[str] = None
    target_id: Optional[int] = None

    if event.event_type in ("challenge.view", "challenge.attempt"):
        target_kind = "challenge"
        target_id = _challenge_id_from_view_args(request)

    payload = {"status_code": response.status_code}

    return ActivityRecord(
        event_type=event.event_type,
        actor_id=actor_id,
        actor_role=_actor_role(user_type),
        team_id=user_team_id,
        target_kind=target_kind,
        target_id=target_id,
        occurred_at=_utc_now(),
        payload=payload,
        request_ip=request.remote_addr,
    )
