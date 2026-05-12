"""Activity logging for the Hikari platform.

A single public entry point, ``register(app)``, wires the package to a Flask
application. Everything else is internal detail.
"""

from .dto import ActivityRecord
from .listeners import register
from .models import HikariActivity
from .recorder import ACTIVITY_TOPIC, persist, publish

__all__ = [
    "ACTIVITY_TOPIC",
    "ActivityRecord",
    "HikariActivity",
    "persist",
    "publish",
    "register",
]
