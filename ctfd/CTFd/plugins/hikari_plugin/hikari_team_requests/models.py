"""Persistence for requests to join a competition team."""

from datetime import datetime

from CTFd.models import db


class TeamMembershipRequest(db.Model):
    """A participant request awaiting a team captain's decision."""

    __tablename__ = "hikari_team_membership_requests"
    __table_args__ = (
        db.UniqueConstraint("team_id", "user_id", name="uq_hikari_team_request"),
    )

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(
        db.Integer,
        db.ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    team = db.relationship("Teams", foreign_keys=[team_id])
    user = db.relationship("Users", foreign_keys=[user_id])
    resolver = db.relationship("Users", foreign_keys=[resolved_by_user_id])
