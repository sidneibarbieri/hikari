"""Aggregations over the hikari_activity table.

Each function is a pure read against the database and returns Pydantic DTOs.
The view layer composes them; this module does not know about HTTP.
"""

from typing import List

from sqlalchemy import func

from CTFd.models import Teams, db
from CTFd.plugins.hikari_plugin.hikari_activity.models import HikariActivity

from .dto import EventCount, RecentEvent, TeamActivity


def total_events() -> int:
    return db.session.query(func.count(HikariActivity.id)).scalar() or 0


def event_counts_by_type() -> List[EventCount]:
    rows = (
        db.session.query(
            HikariActivity.event_type,
            func.count(HikariActivity.id),
        )
        .group_by(HikariActivity.event_type)
        .order_by(func.count(HikariActivity.id).desc())
        .all()
    )
    return [EventCount(label=event_type, count=count) for event_type, count in rows]


def event_counts_by_team(limit: int = 25) -> List[TeamActivity]:
    """Activity counts grouped by team, joined with team names where available."""
    rows = (
        db.session.query(
            HikariActivity.team_id,
            Teams.name,
            func.count(HikariActivity.id),
        )
        .outerjoin(Teams, Teams.id == HikariActivity.team_id)
        .group_by(HikariActivity.team_id, Teams.name)
        .order_by(func.count(HikariActivity.id).desc())
        .limit(limit)
        .all()
    )
    return [
        TeamActivity(team_id=team_id, team_name=team_name, event_count=event_count)
        for team_id, team_name, event_count in rows
    ]


def recent_events(limit: int = 50) -> List[RecentEvent]:
    rows = (
        HikariActivity.query.order_by(HikariActivity.id.desc()).limit(limit).all()
    )
    return [
        RecentEvent(
            id=row.id,
            event_type=row.event_type,
            actor_id=row.actor_id,
            actor_role=row.actor_role,
            team_id=row.team_id,
            target_kind=row.target_kind,
            target_id=row.target_id,
            occurred_at=row.occurred_at,
            request_ip=row.request_ip,
            payload=row.payload,
        )
        for row in rows
    ]


def iter_all_events():
    """Yield every activity row as a RecentEvent in insertion order.

    Used by the JSONL exporter to stream without buffering the whole result
    set in memory.
    """
    query = HikariActivity.query.order_by(HikariActivity.id.asc()).yield_per(500)
    for row in query:
        yield RecentEvent(
            id=row.id,
            event_type=row.event_type,
            actor_id=row.actor_id,
            actor_role=row.actor_role,
            team_id=row.team_id,
            target_kind=row.target_kind,
            target_id=row.target_id,
            occurred_at=row.occurred_at,
            request_ip=row.request_ip,
            payload=row.payload,
        )
