"""Zerotier admin routes — VPN association between teams and networks.

Exposes a single register(blueprint) function the plugin entrypoint calls.
The previous monolithic `load()` had all 8 zerotier routes inline; pulling
them here makes responsibilities visible and the entrypoint smaller without
changing public URL surface.
"""

from .views import register

__all__ = ["register"]
