"""Record a Kibana gateway request as a structured activity event.

The classifier extracts forensic facts from the request body; this module is
responsible for binding those facts to the authenticated actor and writing
the record through the shared persistence + publish path.
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional

from confluent_kafka import KafkaException
from flask import current_app, request
from sqlalchemy.exc import SQLAlchemyError

from CTFd.utils.user import get_current_user, get_ip

from CTFd.plugins.hikari_plugin.hikari_activity.dto import ActivityRecord
from CTFd.plugins.hikari_plugin.hikari_activity import recorder

from .classifier import KibanaQueryFacts, classify


_QUERY_PATH_MARKERS = (
    "api/console/proxy",
    "internal/search",
    "internal/bsearch",
    "api/search",
)
_IGNORED_PATH_MARKERS = (
    "api/content_management/rpc/search",
    "api/core/capabilities",
)
_APP_PATH_MARKERS = (
    "",
    "app/home",
    "app/discover",
    "app/dashboards",
    "app/visualize",
)
_BODY_PREVIEW_LIMIT = 16000


def event_type_for(path: str, method: str, facts: KibanaQueryFacts) -> Optional[str]:
    """Return the activity event_type the path/method/body corresponds to."""
    normalized = path.strip("/")
    if any(marker in normalized for marker in _IGNORED_PATH_MARKERS):
        return None
    if method == "GET" and normalized in _APP_PATH_MARKERS:
        return "kibana.open"
    if method in {"POST", "PUT", "PATCH"}:
        if any(marker in normalized for marker in _QUERY_PATH_MARKERS):
            return "kibana.query"
        if has_investigation_signal(facts):
            return "kibana.query"
    return None


def record_kibana_activity(path: str, method: str, body: bytes, status_code: int) -> None:
    facts = classify(path, method, body)
    event_type = event_type_for(path, method, facts)
    if event_type is None:
        return

    user = get_current_user()
    payload = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "query_string": request.query_string.decode("utf-8", errors="replace"),
        "request_body_sha256": hashlib.sha256(body).hexdigest() if body else None,
        "request_body": _body_preview(body),
        "kibana": facts.dict(exclude_none=True),
    }
    record = ActivityRecord(
        event_type=event_type,
        actor_id=user.id if user else None,
        actor_role="admin" if user and user.type == "admin" else "user",
        team_id=user.team_id if user else None,
        target_kind="kibana",
        target_id=None,
        occurred_at=datetime.now(timezone.utc),
        payload=payload,
        request_ip=get_ip(),
    )

    # Mirror the failure policy from hikari_activity/listeners.py: log the full
    # traceback but let the response reach the user unaffected.
    try:
        recorder.persist(record)
    except SQLAlchemyError:
        current_app.logger.exception(
            "hikari.kibana_activity: persist failed event_type=%s actor_id=%s",
            event_type,
            record.actor_id,
        )
    try:
        recorder.publish(record)
    except (KafkaException, BufferError):
        current_app.logger.exception(
            "hikari.kibana_activity: publish failed event_type=%s actor_id=%s",
            event_type,
            record.actor_id,
        )


def _body_preview(body: bytes) -> Optional[str]:
    if not body:
        return None
    text = body[:_BODY_PREVIEW_LIMIT].decode("utf-8", errors="replace")
    if len(body) > _BODY_PREVIEW_LIMIT:
        return text + "\n[truncated]"
    return text


def has_investigation_signal(facts: KibanaQueryFacts) -> bool:
    return any(
        (
            facts.indices,
            facts.has_query,
            facts.has_filters,
            facts.has_aggs,
            facts.has_sort,
            facts.filter_count,
            facts.must_count,
            facts.should_count,
            facts.must_not_count,
            facts.size is not None,
            facts.time_range_field,
            facts.free_text_excerpt,
        )
    )
