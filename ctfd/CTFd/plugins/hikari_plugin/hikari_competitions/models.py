"""Persistent state for a competition execution in this deployment."""

from datetime import datetime

from CTFd.models import db


class CompetitionRun(db.Model):
    """One scheduled or completed execution in an isolated deployment."""

    __tablename__ = "hikari_competition_runs"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), nullable=False, unique=True, index=True)
    name = db.Column(db.String(128), nullable=False)
    scoring_mode = db.Column(db.String(16), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="draft", index=True)
    duration_minutes = db.Column(db.Integer, nullable=False)
    paused_remaining_seconds = db.Column(db.Integer, nullable=True)
    starts_at = db.Column(db.DateTime, nullable=True, index=True)
    ends_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
