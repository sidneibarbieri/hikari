"""Build ActivityRecord instances from a live Flask request/response pair.

Each builder is a pure function that reads from the request/response and
returns a record. Building is separated from persisting so the listener can
choose to publish only, persist only, or both, without touching this module.
"""

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, Optional

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


def _challenge_id_from_request(request: Request) -> Optional[int]:
    """Read challenge_id from URL view args, JSON body, or form, in that order.

    GET /api/v1/challenges/<challenge_id> exposes it on view_args.
    POST /api/v1/challenges/attempt carries it in the JSON body.
    Form-encoded submissions carry it as a form field.
    """
    if request.view_args:
        view_value = request.view_args.get("challenge_id")
        if view_value is not None:
            return int(view_value)
    if request.is_json:
        body = request.get_json(silent=True) or {}
        body_value = body.get("challenge_id")
        if body_value is not None:
            return int(body_value)
    form_value = request.form.get("challenge_id")
    if form_value is not None:
        return int(form_value)
    return None


def _request_json(request: Request) -> Dict[str, Any]:
    if not request.is_json:
        return {}
    body = request.get_json(silent=True)
    if isinstance(body, dict):
        return body
    return {}


def _response_json(response: Response) -> Dict[str, Any]:
    body = response.get_json(silent=True)
    if isinstance(body, dict):
        return body
    return {}


def _submission_facts(request: Request) -> Dict[str, Any]:
    body = _request_json(request)
    submission = body.get("submission", request.form.get("submission"))
    if submission is None:
        return {}
    value = str(submission)
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return {
        "submission_length": len(value),
        "submission_sha256": digest,
    }


def _challenge_attempt_payload(request: Request, response: Response) -> Dict[str, Any]:
    response_body = _response_json(response)
    data = response_body.get("data")
    result = data.get("status") if isinstance(data, dict) else None
    facts = _submission_facts(request)
    if result is not None:
        facts["result"] = result
    return {"attempt": facts} if facts else {}


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
        target_id = _challenge_id_from_request(request)

    payload: Dict[str, Any] = {"status_code": response.status_code}
    if event.event_type == "challenge.attempt":
        payload.update(_challenge_attempt_payload(request, response))

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
