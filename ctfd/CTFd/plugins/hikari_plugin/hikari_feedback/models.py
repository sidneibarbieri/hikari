from datetime import datetime

from CTFd.models import db


class FeedbackResponse(db.Model):
    __tablename__ = "hikari_feedback_responses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    competition_key = db.Column(db.String(128), nullable=False, index=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    payload = db.Column(db.Text, nullable=False)
    request_ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)

    user = db.relationship("Users", backref=db.backref("hikari_feedback_responses", lazy="dynamic"))
    team = db.relationship("Teams", backref=db.backref("hikari_feedback_responses", lazy="dynamic"))
