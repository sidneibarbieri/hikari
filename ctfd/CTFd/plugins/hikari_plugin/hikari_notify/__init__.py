"""Admin route that broadcasts an e-mail message to selected teams.

Lifted out of the plugin entrypoint so the URL surface evolves
without churning load(). Same blueprint, same URL, same template —
only the registration site moved.
"""

from .views import register

__all__ = ["register"]
