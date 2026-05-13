from typing import List, Optional

from pydantic import BaseModel


class LiveStanding(BaseModel):
    position: int
    account_id: int
    name: str
    score: int
    solves: int
    last_solve_at: Optional[str]


class RecentSolve(BaseModel):
    occurred_at: str
    challenge_name: str
    user_name: str
    team_name: Optional[str]
    value: int


class TimelinePoint(BaseModel):
    occurred_at: str
    team_name: str
    score: int


class LiveBoard(BaseModel):
    generated_at: str
    total_solves: int
    active_teams: int
    active_users: int
    team_standings: List[LiveStanding]
    individual_standings: List[LiveStanding]
    recent_solves: List[RecentSolve]
    timeline: List[TimelinePoint]
