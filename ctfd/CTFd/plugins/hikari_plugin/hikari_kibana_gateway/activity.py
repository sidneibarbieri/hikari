import hashlib
from datetime import datetime, timezone
from typing import Optional

from flask import request

from CTFd.utils.user import get_current_user, get_ip

from CTFd.plugins.hikari_plugin.hikari_activity.dto import ActivityRecord
from CTFd.plugins.hikari_plugin.hikari_activity import recorder


QUERY_PATH_MARKERS = (
    "api/console/proxy",
    "internal/search",
    "internal/bsearch",
    "api/search",
    "api/saved_objects",
)
APP_PATH_MARKERS = (
    "",
    "app/home",
    "app/discover",
    "app/dashboards",
    "app/visualize",
)


def event_type_for(path: str, method: str, body: bytes) -> Optional[str]:
    normalized = path.strip("/")
    if method in {"POST", "PUT", "PATCH"}:
        if any(marker in normalized for marker in QUERY_PATH_MARKERS):
            return "kibana.query"
        if b"query" in body or b"filter" in body:
            return "kibana.query"
    if method == "GET" and normalized in APP_PATH_MARKERS:
        return "kibana.open"
    return None


def record_kibana_activity(path: str, method: str, body: bytes, status_code: int) -> None:
    event_type = event_type_for(path, method, body)
    if event_type is None:
        return

    user = get_current_user()
    payload = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "query_string": request.query_string.decode("utf-8", errors="replace"),
        "request_body_sha256": hashlib.sha256(body).hexdigest() if body else None,
        "request_body": body_preview(body),
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


def body_preview(body: bytes) -> Optional[str]:
    if not body:
        return None
    limit = 16000
    text = body[:limit].decode("utf-8", errors="replace")
    if len(body) > limit:
        return text + "\n[truncated]"
    return text
