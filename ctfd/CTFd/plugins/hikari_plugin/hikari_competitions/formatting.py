"""Presentation helpers for the execution console."""

MINUTES_PER_HOUR = 60


def describe_duration(total_minutes: int) -> str:
    """State a duration the way an operator reads it aloud."""
    hours, minutes = divmod(total_minutes, MINUTES_PER_HOUR)
    if hours and minutes:
        return f"{hours}h{minutes:02d}"
    if hours:
        return f"{hours}h"
    return f"{minutes} min"
