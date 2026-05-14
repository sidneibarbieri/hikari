"""DTO for a feedback submission.

The response is stored as JSON so the questionnaire can evolve without a
database migration for every new analytical field.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, conint, validator


_PHASES = {"post"}

_PRIMARY_ROLES = {
    "student",
    "soc_analyst_t1",
    "soc_analyst_t2",
    "incident_responder",
    "threat_hunter",
    "forensics_analyst",
    "educator",
    "researcher",
    "other",
}

_FORMAL_EDUCATION = {
    "none",
    "on_the_job",
    "vendor_certification",
    "undergraduate_computing",
    "undergraduate_cyber",
    "postgraduate_computing",
    "postgraduate_cyber",
    "other",
}

_MITRE_TACTICS = {
    "reconnaissance",
    "resource_development",
    "initial_access",
    "execution",
    "persistence",
    "privilege_escalation",
    "defense_evasion",
    "credential_access",
    "discovery",
    "lateral_movement",
    "collection",
    "command_and_control",
    "exfiltration",
    "impact",
}


Score5 = conint(ge=1, le=5)
Score7 = conint(ge=1, le=7)
Score10 = conint(ge=0, le=10)


class FeedbackPayload(BaseModel):
    """Single questionnaire response."""

    # Identification
    phase: str

    # Background and prior experience
    years_cyber_experience: Optional[str] = None
    primary_role: Optional[str] = None
    prior_ctf_count: Optional[str] = None
    years_soc_experience: Optional[str] = None
    formal_education: Optional[str] = None

    # Role-based self-assessment (1-5)
    self_cyber_defense_analyst: Optional[Score5] = None
    self_incident_responder: Optional[Score5] = None
    self_threat_warning_analyst: Optional[Score5] = None
    self_forensics_analyst: Optional[Score5] = None
    self_vuln_assessment_analyst: Optional[Score5] = None

    # Tool fluency (1-5)
    tool_kibana: Optional[Score5] = None
    tool_kql: Optional[Score5] = None
    tool_attack_framework: Optional[Score5] = None
    tool_other_siem: Optional[Score5] = None

    # Attack-chain tactics practised (multiselect)
    mitre_tactics_practised: List[str] = Field(default_factory=list)

    # Task load (1-7)
    tlx_mental_demand: Optional[Score7] = None
    tlx_temporal_demand: Optional[Score7] = None
    tlx_performance: Optional[Score7] = None
    tlx_effort: Optional[Score7] = None
    tlx_frustration: Optional[Score7] = None

    # Usability (1-5)
    sus_would_use_frequently: Optional[Score5] = None
    sus_unnecessarily_complex: Optional[Score5] = None
    sus_easy_to_use: Optional[Score5] = None
    sus_needed_support: Optional[Score5] = None
    sus_functions_well_integrated: Optional[Score5] = None
    sus_too_much_inconsistency: Optional[Score5] = None
    sus_quick_to_learn: Optional[Score5] = None
    sus_cumbersome: Optional[Score5] = None
    sus_felt_confident: Optional[Score5] = None
    sus_needed_to_learn_a_lot: Optional[Score5] = None

    # Learning outcomes (perceived improvement 1-5)
    learning_log_analysis: Optional[Score5] = None
    learning_pattern_correlation: Optional[Score5] = None
    learning_hypothesis_generation: Optional[Score5] = None
    learning_tool_fluency: Optional[Score5] = None
    learning_time_to_detect: Optional[Score5] = None
    learning_documentation: Optional[Score5] = None

    # Scenario realism and methodological coherence (1-5)
    realism_attack_chain: Optional[Score5] = None
    realism_telemetry: Optional[Score5] = None
    realism_pace: Optional[Score5] = None
    methodology_coherence: Optional[Score5] = None

    # Recommendation score (0-10)
    nps_recommend: Optional[Score10] = None

    # Qualitative reflections (free text)
    most_valuable_technique: Optional[str] = None
    biggest_learning_blocker: Optional[str] = None
    suggested_scenarios: Optional[str] = None
    other_comments: Optional[str] = None

    @validator("phase")
    def validate_phase(cls, value):
        return _ensure_in(value, _PHASES, "phase")

    @validator("primary_role")
    def validate_primary_role(cls, value):
        return _ensure_in(value, _PRIMARY_ROLES, "primary_role") if value else value

    @validator("formal_education")
    def validate_formal_education(cls, value):
        return _ensure_in(value, _FORMAL_EDUCATION, "formal_education") if value else value

    @validator("mitre_tactics_practised", each_item=True)
    def validate_mitre_tactic(cls, value):
        return _ensure_in(value, _MITRE_TACTICS, "mitre_tactic")


def _ensure_in(value, allowed, field_name):
    if value not in allowed:
        raise ValueError(f"invalid {field_name}: {value}")
    return value
