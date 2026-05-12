"""Pydantic data transfer object for activity records.

ActivityRecord is the contract between the listeners that observe Flask
requests, the persistence layer that writes to the relational store, and the
publisher that sends to Kafka. Keeping a dedicated DTO decouples the wire
format from the storage schema and lets callers build a record without
importing SQLAlchemy.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class ActivityRecord(BaseModel):
    """A single observed action performed against the platform."""

    event_type: str
    actor_id: Optional[int] = None
    actor_role: Optional[str] = None
    team_id: Optional[int] = None
    target_kind: Optional[str] = None
    target_id: Optional[int] = None
    occurred_at: datetime
    payload: Optional[Dict[str, Any]] = None
    request_ip: Optional[str] = None

    class Config:
        # Allow building from SQLAlchemy row objects via from_orm().
        orm_mode = True
