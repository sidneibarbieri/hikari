from typing import List, Optional

from pydantic import BaseModel, conint, validator


class FeedbackPayload(BaseModel):
    phase: str
    experience_level: str
    prior_ctf: bool
    blue_team_familiarity: str
    interface_rating: conint(ge=1, le=5)
    challenge_difficulty: str
    dashboard_relevance: str
    useful_dashboard_elements: str
    unused_dashboard_elements: str
    technical_issues: bool
    technical_issue_notes: Optional[str] = None
    learning_effectiveness: conint(ge=1, le=5)
    learned_areas: List[str]
    operational_confidence_before: conint(ge=1, le=5)
    operational_confidence_after: conint(ge=1, le=5)
    realism: str
    methodology_notes: Optional[str] = None
    suggested_improvements: Optional[str] = None

    @validator("phase")
    def validate_phase(cls, value):
        return validate_choice(value, {"pre", "post", "followup"})

    @validator("experience_level")
    def validate_experience_level(cls, value):
        return validate_choice(value, {"beginner", "intermediate", "advanced", "specialist"})

    @validator("blue_team_familiarity")
    def validate_blue_team_familiarity(cls, value):
        return validate_choice(value, {"none", "low", "moderate", "high"})

    @validator("challenge_difficulty")
    def validate_challenge_difficulty(cls, value):
        return validate_choice(value, {"too_easy", "easy", "adequate", "hard", "too_hard"})

    @validator("dashboard_relevance")
    def validate_dashboard_relevance(cls, value):
        return validate_choice(value, {"high", "partial", "low", "none"})

    @validator("realism")
    def validate_realism(cls, value):
        return validate_choice(value, {"high", "partial", "low", "none"})

    @validator("learned_areas")
    def validate_learned_areas(cls, value):
        allowed = {
            "log_analysis",
            "intrusion_detection",
            "incident_response",
            "digital_forensics",
            "threat_intelligence",
            "collaboration",
        }
        invalid = set(value) - allowed
        if invalid:
            raise ValueError(f"invalid learned areas: {sorted(invalid)}")
        return value


def validate_choice(value, allowed):
    if value not in allowed:
        raise ValueError(f"invalid choice: {value}")
    return value
