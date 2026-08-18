"""Resolve the identifier of the execution active in this installation."""


from CTFd.utils import get_config


from CTFd.plugins.hikari_plugin.settings import settings


def current_competition_key() -> str:
    """Return the configured execution key with a stable local fallback."""
    configured_key = get_config("hikari_competition_key")
    if configured_key:
        return configured_key
    return settings().competition_key
