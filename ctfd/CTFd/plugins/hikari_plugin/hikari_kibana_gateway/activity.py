"""Record a Kibana gateway request as a structured activity event.

The classifier extracts forensic facts from the request body; this module is
responsible for binding those facts to the authenticated actor and writing
the record through the shared persistence + publish path.
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional

from flask import request

from CTFd.utils.user import get_current_user, get_ip

from CTFd.plugins.hikari_plugin.hikari_activity.dto import ActivityRecord
from CTFd.plugins.hikari_plugin.hikari_activity import recorder

from .classifier import classify


_QUERY_PATH_MARKERS = (
    "api/console/proxy",
    "internal/search",
    "internal/bsearch",
    "api/search",
    "api/saved_objects",
)
_APP_PATH_MARKERS = (
    "",
    "app/home",
    "app/discover",
    "app/dashboards",
    "app/visualize",
)
_BODY_PREVIEW_LIMIT = 16000


def event_type_for(path: str, method: str, body: bytes) -> Optional[str]:
    """Return the activity event_type the path/method/body corresponds to."""
    normalized = path.strip("/")
    if method in {"POST", "PUT", "PATCH"}:
        if any(marker in normalized for marker in _QUERY_PATH_MARKERS):
            return "kibana.query"
        if b"query" in body or b"filter" in body:
            return "kibana.query"
    if method == "GET" and normalized in _APP_PATH_MARKERS:
        return "kibana.open"
    return None


def record_kibana_activity(path: str, method: str, body: bytes, status_code: int) -> None:
    event_type = event_type_for(path, method, body)
    if event_type is None:
        return

    user = get_current_user()
    facts = classify(path, method, body)
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

    recorder.persist(record)
    recorder.publish(record)


def _body_preview(body: bytes) -> Optional[str]:
    if not body:
        return None
    text = body[:_BODY_PREVIEW_LIMIT].decode("utf-8", errors="replace")
    if len(body) > _BODY_PREVIEW_LIMIT:
        return text + "\n[truncated]"
    return text
