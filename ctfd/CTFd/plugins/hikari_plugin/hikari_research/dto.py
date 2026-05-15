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


class FeedbackCount(BaseModel):
    label: str
    count: int


class FeedbackMetric(BaseModel):
    label: str
    average: float
    count: int


class FeedbackSummary(BaseModel):
    total_responses: int
    roles: List[FeedbackCount]
    metrics: List[FeedbackMetric]


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


class SubmissionPattern(BaseModel):
    """Per-challenge aggregate of how solvers reached the answer.

    The four buckets discriminate the two extremes the artifact paper
    cares about: organic discovery (1 attempt → solve) vs. brute-force
    grinding (many failures before solve). Bucket boundaries are chosen
    to match a defender's reasoning: 1 is "knew it"; 2–5 is reasonable
    iteration; 6–20 is exhaustive search; 20+ is grinding.
    """

    challenge_id: int
    challenge_name: str
    category: Optional[str]
    solvers: int
    organic: int       # solve on first try
    exploratory: int   # 2–5 attempts before solve
    brute_force: int   # 6–20 attempts before solve
    grinding: int      # 21+ attempts before solve
    median_attempts: int
    total_failures: int


class TeamSubmissionPosture(BaseModel):
    """How does each team interact with the scoreboard?

    ``brute_force_ratio`` is failures per solve — a team with many
    failures and few solves shows brute-force discipline; a team with
    one failure per solve is reading the data and thinking.
    """

    team_id: Optional[int]
    team_name: Optional[str]
    solves: int
    failures: int
    brute_force_ratio: float
    median_seconds_between_attempts: Optional[int]


class HuntingDepth(BaseModel):
    """Per-actor depth-of-investigation signal from the Kibana gateway.

    Aggregates the classification facts the gateway already records
    (``hikari_activity.payload.kibana``) so the admin can see who is
    exploring vs. who is just opening the dashboard.
    """

    actor_id: Optional[int]
    actor_role: Optional[str]
    team_id: Optional[int]
    total_requests: int
    distinct_indices: int
    distinct_kql_queries: int
    discover_queries: int
    saved_object_views: int


class ResearchSummary(BaseModel):
    filters: ResearchFilters
    total_events: int
    events_by_type: List[EventCount]
    teams_by_event_count: List[TeamActivity]
    submission_patterns: List[SubmissionPattern]
    team_postures: List[TeamSubmissionPosture]
    hunting_depth: List[HuntingDepth]
    feedback: FeedbackSummary
    available_event_types: List[str]
    recent: List[RecentEvent]
