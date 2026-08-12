"""Forward-only schema updates for competition execution state."""

from sqlalchemy import inspect, text

from CTFd.models import db


def ensure_competition_schema() -> None:
    """Add pause state storage to executions created by earlier builds."""
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    if "hikari_competition_runs" not in table_names:
        return

    column_names = {
        column["name"]
        for column in inspector.get_columns("hikari_competition_runs")
    }
    if "paused_remaining_seconds" in column_names:
        return

    db.session.execute(
        text(
            "ALTER TABLE hikari_competition_runs "
            "ADD COLUMN paused_remaining_seconds INTEGER NULL"
        )
    )
    db.session.commit()
