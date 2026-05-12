"""Register the Flask before/after_request hooks that emit activity records.

The listener is the only seam between activity logging and the rest of the
application. Everything else in this package is pure or only depends on the
plugin's own modules. The listener also defines the failure policy: a problem
recording the activity must not break the user-visible request.
"""

from typing import Optional, Tuple

from confluent_kafka import KafkaException
from flask import Flask, Response, current_app, g, request, session
from sqlalchemy.exc import SQLAlchemyError

from CTFd.models import Users

from . import builders
from . import event_map
from . import recorder
from .event_map import ActorResolution


_ACTOR_BEFORE_KEY = "_hikari_actor_id_before"


def _stash_pre_request_actor() -> None:
    actor_id = session.get("id")
    setattr(g, _ACTOR_BEFORE_KEY, actor_id)


def _resolve_actor_id(resolution: ActorResolution) -> Optional[int]:
    if resolution is ActorResolution.BEFORE_REQUEST:
        return getattr(g, _ACTOR_BEFORE_KEY, None)
    return session.get("id")


def _resolve_actor_attrs(actor_id: Optional[int]) -> Tuple[Optional[str], Optional[int]]:
    """Return (user_type, team_id) for the actor, or (None, None) if absent."""
    if actor_id is None:
        return None, None
    user = Users.query.filter_by(id=actor_id).first()
    if user is None:
        return None, None
    return user.type, user.team_id


def _emit(response: Response) -> Response:
    endpoint = request.endpoint
    if endpoint is None:
        return response

    event = event_map.ENDPOINT_TO_EVENT.get(endpoint)
    if event is None:
        return response
    if request.method not in event.captured_methods:
        return response
    if response.status_code not in event.captured_status_codes:
        return response

    actor_id = _resolve_actor_id(event.actor_resolution)
    user_type, team_id = _resolve_actor_attrs(actor_id)
    record = builders.build_record(
        event=event,
        request=request,
        response=response,
        actor_id=actor_id,
        user_type=user_type,
        user_team_id=team_id,
    )

    # Activity logging must never break the user-visible request, so the
    # storage and publish paths are caught at the boundary. Each catch names
    # the concrete exception type — broad ``except Exception`` would hide
    # real bugs behind the same log line that legitimate I/O failures use.
    try:
        recorder.persist(record)
    except SQLAlchemyError:
        current_app.logger.exception(
            "hikari.activity: persist failed for %s", event.event_type
        )

    try:
        recorder.publish(record)
    except (KafkaException, BufferError):
        current_app.logger.exception(
            "hikari.activity: publish failed for %s", event.event_type
        )

    return response


def register(app: Flask) -> None:
    """Attach the activity emitter to the application's request lifecycle."""
    app.before_request(_stash_pre_request_actor)
    app.after_request(_emit)
