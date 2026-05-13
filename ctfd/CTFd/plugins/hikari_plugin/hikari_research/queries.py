"""Aggregations over the hikari_activity table.

Each function is a pure read against the database and returns Pydantic DTOs.
The view layer composes them; this module is independent from HTTP.
"""

from typing import List, Optional

from sqlalchemy import func

from CTFd.models import Teams, db
from CTFd.plugins.hikari_plugin.hikari_activity.models import HikariActivity

from .dto import EventCount, RecentEvent, ResearchFilters, TeamActivity


def _filtered_activity_query(filters: Optional[ResearchFilters] = None):
    query = HikariActivity.query
    if filters is None:
        return query
    if filters.event_type:
        query = query.filter(HikariActivity.event_type == filters.event_type)
    if filters.actor_id is not None:
        query = query.filter(HikariActivity.actor_id == filters.actor_id)
    if filters.team_id is not None:
        query = query.filter(HikariActivity.team_id == filters.team_id)
    return query


def total_events(filters: Optional[ResearchFilters] = None) -> int:
    return _filtered_activity_query(filters).count()


def available_event_types() -> List[str]:
    rows = (
        db.session.query(HikariActivity.event_type)
        .group_by(HikariActivity.event_type)
        .order_by(HikariActivity.event_type.asc())
        .all()
    )
    return [event_type for (event_type,) in rows]


def event_counts_by_type(filters: Optional[ResearchFilters] = None) -> List[EventCount]:
    rows = (
        _filtered_activity_query(filters)
        .with_entities(
            HikariActivity.event_type,
            func.count(HikariActivity.id),
        )
        .group_by(HikariActivity.event_type)
        .order_by(func.count(HikariActivity.id).desc())
        .all()
    )
    return [EventCount(label=event_type, count=count) for event_type, count in rows]


def event_counts_by_team(
    filters: Optional[ResearchFilters] = None,
    limit: int = 25,
) -> List[TeamActivity]:
    """Activity counts grouped by team, joined with team names where available."""
    rows = (
        _filtered_activity_query(filters)
        .with_entities(
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


def recent_events(
    filters: Optional[ResearchFilters] = None,
    limit: int = 50,
) -> List[RecentEvent]:
    rows = (
        _filtered_activity_query(filters)
        .order_by(HikariActivity.id.desc())
        .limit(limit)
        .all()
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


def iter_all_events(filters: Optional[ResearchFilters] = None):
    """Yield every activity row as a RecentEvent in insertion order.

    Used by the JSONL exporter to stream without buffering the whole result
    set in memory.
    """
    query = (
        _filtered_activity_query(filters)
        .order_by(HikariActivity.id.asc())
        .yield_per(500)
    )
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
