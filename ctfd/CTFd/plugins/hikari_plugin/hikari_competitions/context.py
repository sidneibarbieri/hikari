"""Resolve the identifier of the execution active in this installation."""

import os

from CTFd.utils import get_config


DEFAULT_COMPETITION_KEY = "local"


def current_competition_key() -> str:
    """Return the configured execution key with a stable local fallback."""
    configured_key = get_config("hikari_competition_key")
    if configured_key:
        return configured_key
    return os.environ.get("HIKARI_COMPETITION_KEY", DEFAULT_COMPETITION_KEY)
