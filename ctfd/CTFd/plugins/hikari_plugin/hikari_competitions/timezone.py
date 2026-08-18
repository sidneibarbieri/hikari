"""Operator-facing time conversion for competition schedules."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from CTFd.plugins.hikari_plugin.settings import settings


def operator_time_zone() -> ZoneInfo:
    """Return the deployment time zone configured for schedule entry."""
    return ZoneInfo(settings().time_zone)


def parse_local_schedule(value: str) -> datetime:
    """Convert a datetime-local form value to a naive UTC timestamp."""
    local_time = datetime.strptime(value, "%Y-%m-%dT%H:%M")
    return local_time.replace(tzinfo=operator_time_zone()).astimezone(
        timezone.utc
    ).replace(tzinfo=None)


def format_schedule_time(value: datetime | None) -> str:
    """Render a stored UTC timestamp in the operator time zone."""
    if value is None:
        return "-"
    utc_time = value.replace(tzinfo=timezone.utc)
    return utc_time.astimezone(operator_time_zone()).strftime("%d/%m/%Y %H:%M")
