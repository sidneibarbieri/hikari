"""Pydantic shapes returned by the research queries.

These DTOs are what the view layer renders and what the JSONL exporter
streams. They are intentionally distinct from the storage model so the
shape of the analytics surface can change without touching the schema.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class EventCount(BaseModel):
    label: str
    count: int


class TeamActivity(BaseModel):
    team_id: Optional[int]
    team_name: Optional[str]
    event_count: int


class RecentEvent(BaseModel):
    id: int
    event_type: str
    actor_id: Optional[int]
    actor_role: Optional[str]
    team_id: Optional[int]
    target_kind: Optional[str]
    target_id: Optional[int]
    occurred_at: datetime
    request_ip: Optional[str]
    payload: Optional[Dict[str, Any]] = None


class ResearchFilters(BaseModel):
    event_type: Optional[str] = None
    actor_id: Optional[int] = None
    team_id: Optional[int] = None


class ResearchSummary(BaseModel):
    filters: ResearchFilters
    total_events: int
    events_by_type: List[EventCount]
    teams_by_event_count: List[TeamActivity]
    available_event_types: List[str]
    recent: List[RecentEvent]
