"""Small forward-only schema upgrades for the Hikari activity store."""

from sqlalchemy import inspect, text

from CTFd.models import db


def ensure_activity_schema() -> None:
    """Add the execution key column to activity stores created before it existed."""
    inspector = inspect(db.engine)
    column_names = {column["name"] for column in inspector.get_columns("hikari_activity")}
    if "competition_key" in column_names:
        return

    db.session.execute(
        text(
            "ALTER TABLE hikari_activity "
            "ADD COLUMN competition_key VARCHAR(64) NOT NULL DEFAULT 'local'"
        )
    )
    db.session.execute(
        text(
            "CREATE INDEX ix_hikari_activity_competition_key "
            "ON hikari_activity (competition_key)"
        )
    )
    db.session.commit()
