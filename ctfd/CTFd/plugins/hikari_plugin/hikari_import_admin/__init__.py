"""Admin route that accepts a Hikari backup ZIP and replays it.

Wraps hikari_importer.HikariImporter behind the /admin/import-hikari-ctf
form. Extracted from the plugin entrypoint to keep load() scannable.
"""

from .views import register

__all__ = ["register"]
