from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, SelectMultipleField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, NumberRange
from wtforms import IntegerField

from CTFd.forms import CTFdCSRF


class FeedbackForm(FlaskForm):
    class Meta:
        csrf = True
        csrf_class = CTFdCSRF
        csrf_field_name = "nonce"

    phase = SelectField(
        "Moment",
        choices=[
            ("pre", "Before the exercise"),
            ("post", "After the exercise"),
            ("followup", "Follow-up"),
        ],
        validators=[DataRequired()],
    )
    experience_level = SelectField(
        "Security experience",
        choices=[
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
            ("specialist", "Specialist"),
        ],
        validators=[DataRequired()],
    )
    prior_ctf = BooleanField("I have participated in CTF exercises before")
    blue_team_familiarity = SelectField(
        "Blue-team familiarity",
        choices=[
            ("none", "None"),
            ("low", "Low"),
            ("moderate", "Moderate"),
            ("high", "High"),
        ],
        validators=[DataRequired()],
    )
    interface_rating = IntegerField(
        "Interface rating",
        validators=[InputRequired(), NumberRange(min=1, max=5)],
    )
    challenge_difficulty = SelectField(
        "Challenge difficulty",
        choices=[
            ("too_easy", "Too easy"),
            ("easy", "Easy"),
            ("adequate", "Adequate"),
            ("hard", "Hard"),
            ("too_hard", "Too hard"),
        ],
        validators=[DataRequired()],
    )
    dashboard_relevance = SelectField(
        "Dashboard relevance",
        choices=[
            ("high", "High"),
            ("partial", "Partial"),
            ("low", "Low"),
            ("none", "None"),
        ],
        validators=[DataRequired()],
    )
    useful_dashboard_elements = TextAreaField("Useful dashboard elements")
    unused_dashboard_elements = TextAreaField("Unused dashboard elements")
    technical_issues = BooleanField("I encountered technical issues")
    technical_issue_notes = TextAreaField("Technical issue notes")
    learning_effectiveness = IntegerField(
        "Learning effectiveness",
        validators=[InputRequired(), NumberRange(min=1, max=5)],
    )
    learned_areas = SelectMultipleField(
        "Learned areas",
        choices=[
            ("log_analysis", "Log analysis"),
            ("intrusion_detection", "Intrusion detection"),
            ("incident_response", "Incident response"),
            ("digital_forensics", "Digital forensics"),
            ("threat_intelligence", "Threat intelligence"),
            ("collaboration", "Team collaboration"),
        ],
        validators=[DataRequired()],
    )
    operational_confidence_before = IntegerField(
        "Operational confidence before",
        validators=[InputRequired(), NumberRange(min=1, max=5)],
    )
    operational_confidence_after = IntegerField(
        "Operational confidence after",
        validators=[InputRequired(), NumberRange(min=1, max=5)],
    )
    realism = SelectField(
        "Scenario realism",
        choices=[
            ("high", "High"),
            ("partial", "Partial"),
            ("low", "Low"),
            ("none", "None"),
        ],
        validators=[DataRequired()],
    )
    methodology_notes = TextAreaField("Threat-hunting method used")
    suggested_improvements = TextAreaField("Suggested improvements")
    submit = SubmitField("Submit")
