"""SQLAlchemy model for the activity log table.

This is the system of record. The Kafka publisher writes to a parallel index
for offline analysis, but persistence here is what makes a record durable.
"""

from CTFd.models import db


class HikariActivity(db.Model):
    """One row per observed action in the platform."""

    __tablename__ = "hikari_activity"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    actor_id = db.Column(db.Integer, nullable=True, index=True)
    actor_role = db.Column(db.String(16), nullable=True)
    team_id = db.Column(db.Integer, nullable=True, index=True)
    target_kind = db.Column(db.String(32), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    occurred_at = db.Column(db.DateTime, nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=True)
    request_ip = db.Column(db.String(45), nullable=True)
