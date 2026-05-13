"""WTForms binding for the research-grade feedback questionnaire.

The form is flat by design — every field is rendered in the template by
walking ``FIELD_GROUPS`` so the visual grouping lives next to the
instrument it implements, not in the storage layer. Optional fields keep
``validators`` minimal; the Pydantic DTO is the authoritative gate.
"""

from typing import Iterable, List, Tuple

from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, SelectMultipleField, SubmitField, TextAreaField, widgets
from wtforms.validators import DataRequired, NumberRange, Optional as OptionalValidator

from CTFd.forms import CTFdCSRF


PHASES = [
    ("pre", "Before the exercise"),
    ("post", "After the exercise"),
    ("followup", "Follow-up (weeks later)"),
]

YEARS_BANDS = [
    ("", "—"),
    ("none", "No prior experience"),
    ("lt_1", "Less than 1 year"),
    ("1_2", "1 to 2 years"),
    ("3_5", "3 to 5 years"),
    ("6_10", "6 to 10 years"),
    ("gt_10", "More than 10 years"),
]

PRIMARY_ROLES = [
    ("", "—"),
    ("student", "Student"),
    ("soc_analyst_t1", "SOC analyst, tier 1"),
    ("soc_analyst_t2", "SOC analyst, tier 2 or above"),
    ("incident_responder", "Incident responder"),
    ("threat_hunter", "Threat hunter"),
    ("forensics_analyst", "Forensics analyst"),
    ("educator", "Educator / instructor"),
    ("researcher", "Researcher"),
    ("other", "Other"),
]

PRIOR_CTF_BANDS = [
    ("", "—"),
    ("0", "None"),
    ("1_3", "1 to 3 events"),
    ("4_10", "4 to 10 events"),
    ("gt_10", "More than 10 events"),
]

FORMAL_EDUCATION = [
    ("", "—"),
    ("none", "None"),
    ("on_the_job", "On-the-job only"),
    ("vendor_certification", "Vendor certifications"),
    ("undergraduate_in_cyber", "Undergraduate degree in cybersecurity"),
    ("postgraduate_in_cyber", "Postgraduate degree in cybersecurity"),
]

MITRE_TACTICS = [
    ("reconnaissance", "Reconnaissance"),
    ("resource_development", "Resource development"),
    ("initial_access", "Initial access"),
    ("execution", "Execution"),
    ("persistence", "Persistence"),
    ("privilege_escalation", "Privilege escalation"),
    ("defense_evasion", "Defense evasion"),
    ("credential_access", "Credential access"),
    ("discovery", "Discovery"),
    ("lateral_movement", "Lateral movement"),
    ("collection", "Collection"),
    ("command_and_control", "Command and control"),
    ("exfiltration", "Exfiltration"),
    ("impact", "Impact"),
]


class _MultiCheckbox(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


def _score5(label):
    return IntegerField(label, validators=[OptionalValidator(), NumberRange(min=1, max=5)])


def _score7(label):
    return IntegerField(label, validators=[OptionalValidator(), NumberRange(min=1, max=7)])


def _score10(label):
    return IntegerField(label, validators=[OptionalValidator(), NumberRange(min=0, max=10)])


def _optional_select(label, choices):
    return SelectField(label, choices=choices, validators=[OptionalValidator()])


class FeedbackForm(FlaskForm):
    class Meta:
        csrf = True
        csrf_class = CTFdCSRF
        csrf_field_name = "nonce"

    phase = SelectField("Moment", choices=PHASES, validators=[DataRequired()])

    years_cyber_experience = _optional_select("Years in cybersecurity", YEARS_BANDS)
    primary_role = _optional_select("Primary role", PRIMARY_ROLES)
    prior_ctf_count = _optional_select("Prior CTF events", PRIOR_CTF_BANDS)
    years_soc_experience = _optional_select("Years in a SOC or equivalent", YEARS_BANDS)
    formal_education = _optional_select("Formal cybersecurity education", FORMAL_EDUCATION)

    self_cyber_defense_analyst = _score5("Cyber Defense Analyst (NICE PR-CDA-001)")
    self_incident_responder = _score5("Cyber Defense Incident Responder (NICE PR-CIR-001)")
    self_threat_warning_analyst = _score5("Threat/Warning Analyst (NICE AN-TWA-001)")
    self_forensics_analyst = _score5("Cyber Defense Forensics Analyst (NICE IN-FOR-001)")
    self_vuln_assessment_analyst = _score5("Vulnerability Assessment Analyst (NICE PR-VAM-001)")

    tool_kibana = _score5("Kibana / Elastic")
    tool_kql = _score5("KQL query writing")
    tool_attack_framework = _score5("MITRE ATT&CK navigation")
    tool_other_siem = _score5("Other SIEM (Splunk, Sentinel, ...)")

    mitre_tactics_practised = _MultiCheckbox(
        "Tactics you exercised during this run",
        choices=MITRE_TACTICS,
        validators=[OptionalValidator()],
    )

    tlx_mental_demand = _score7("Mental demand (NASA-TLX)")
    tlx_temporal_demand = _score7("Temporal demand (NASA-TLX)")
    tlx_performance = _score7("Performance (NASA-TLX, 1 = success, 7 = failure)")
    tlx_effort = _score7("Effort (NASA-TLX)")
    tlx_frustration = _score7("Frustration (NASA-TLX)")

    sus_would_use_frequently = _score5("I would use this system frequently (SUS-1)")
    sus_unnecessarily_complex = _score5("I found it unnecessarily complex (SUS-2)")
    sus_easy_to_use = _score5("I thought it was easy to use (SUS-3)")
    sus_needed_support = _score5("I would need technical support to use it (SUS-4)")
    sus_functions_well_integrated = _score5("The functions are well integrated (SUS-5)")
    sus_too_much_inconsistency = _score5("There was too much inconsistency (SUS-6)")
    sus_quick_to_learn = _score5("Most people would learn it quickly (SUS-7)")
    sus_cumbersome = _score5("I found it cumbersome to use (SUS-8)")
    sus_felt_confident = _score5("I felt confident using the system (SUS-9)")
    sus_needed_to_learn_a_lot = _score5("I had to learn a lot before using it (SUS-10)")

    learning_log_analysis = _score5("Improvement: log analysis")
    learning_pattern_correlation = _score5("Improvement: cross-source correlation")
    learning_hypothesis_generation = _score5("Improvement: hypothesis generation")
    learning_tool_fluency = _score5("Improvement: tool fluency (Kibana, KQL)")
    learning_time_to_detect = _score5("Improvement: time-to-detect")
    learning_documentation = _score5("Improvement: investigation documentation")

    realism_attack_chain = _score5("Realism of the attack chain")
    realism_telemetry = _score5("Realism of the telemetry")
    realism_pace = _score5("Realism of pace and pressure")
    methodology_coherence = _score5("Methodological coherence of the exercise")

    nps_recommend = _score10("How likely are you to recommend Hikari? (0-10)")

    most_valuable_technique = TextAreaField(
        "The single most valuable technique or methodology you used",
        validators=[OptionalValidator()],
    )
    biggest_learning_blocker = TextAreaField(
        "The biggest block to your learning during this run",
        validators=[OptionalValidator()],
    )
    suggested_scenarios = TextAreaField(
        "Scenarios you would like to face next",
        validators=[OptionalValidator()],
    )
    other_comments = TextAreaField(
        "Anything else worth recording",
        validators=[OptionalValidator()],
    )

    submit = SubmitField("Submit feedback")


# Visual grouping for the template. Each tuple is (section_id, title,
# description, list of field names). The template walks this and renders
# matching form fields in order.
FIELD_GROUPS: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...] = (
    (
        "moment",
        "Moment of submission",
        "Which point in the cycle this response refers to. Pre-event responses anchor the baseline; post-event responses are the analytical core.",
        ("phase",),
    ),
    (
        "background",
        "Background and prior exposure",
        "Captured once, before the exercise; later phases may refresh.",
        (
            "years_cyber_experience",
            "primary_role",
            "prior_ctf_count",
            "years_soc_experience",
            "formal_education",
        ),
    ),
    (
        "nice_self",
        "Self-assessed competency (NIST NICE)",
        "Rate your competency for each NICE work role on a 1-5 scale (1 = no familiarity, 5 = expert).",
        (
            "self_cyber_defense_analyst",
            "self_incident_responder",
            "self_threat_warning_analyst",
            "self_forensics_analyst",
            "self_vuln_assessment_analyst",
        ),
    ),
    (
        "tool_fluency",
        "Tool fluency",
        "1 = never used, 5 = teach others.",
        (
            "tool_kibana",
            "tool_kql",
            "tool_attack_framework",
            "tool_other_siem",
        ),
    ),
    (
        "tactics",
        "MITRE ATT&CK tactics practised",
        "Mark the kill-chain stages you exercised during this run.",
        ("mitre_tactics_practised",),
    ),
    (
        "tlx",
        "NASA Task Load Index",
        "Post-event only. 1 = very low, 7 = very high.",
        (
            "tlx_mental_demand",
            "tlx_temporal_demand",
            "tlx_performance",
            "tlx_effort",
            "tlx_frustration",
        ),
    ),
    (
        "sus",
        "System Usability Scale (Brooke, 1986)",
        "Post-event only. 1 = strongly disagree, 5 = strongly agree.",
        (
            "sus_would_use_frequently",
            "sus_unnecessarily_complex",
            "sus_easy_to_use",
            "sus_needed_support",
            "sus_functions_well_integrated",
            "sus_too_much_inconsistency",
            "sus_quick_to_learn",
            "sus_cumbersome",
            "sus_felt_confident",
            "sus_needed_to_learn_a_lot",
        ),
    ),
    (
        "learning",
        "Perceived skill improvement",
        "Post-event only. 1 = no change, 5 = substantial improvement.",
        (
            "learning_log_analysis",
            "learning_pattern_correlation",
            "learning_hypothesis_generation",
            "learning_tool_fluency",
            "learning_time_to_detect",
            "learning_documentation",
        ),
    ),
    (
        "realism",
        "Realism and methodology",
        "Post-event only. 1 = not realistic / incoherent, 5 = matches real operations.",
        (
            "realism_attack_chain",
            "realism_telemetry",
            "realism_pace",
            "methodology_coherence",
        ),
    ),
    (
        "advocacy",
        "Advocacy",
        "Post-event only.",
        ("nps_recommend",),
    ),
    (
        "reflections",
        "Qualitative reflections",
        "Free text. Optional but valuable.",
        (
            "most_valuable_technique",
            "biggest_learning_blocker",
            "suggested_scenarios",
            "other_comments",
        ),
    ),
)


def iter_groups(form: FeedbackForm) -> Iterable[Tuple[str, str, str, List]]:
    for section_id, title, description, names in FIELD_GROUPS:
        fields = [getattr(form, name) for name in names]
        yield section_id, title, description, fields
