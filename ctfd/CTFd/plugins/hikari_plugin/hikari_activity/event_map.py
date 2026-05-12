"""Static mapping from Flask endpoint names to activity event types.

Endpoints that are not in this map are not observed. This is deliberate:
activity logging is opt-in by route so a typo in an endpoint name results in
silently no record, not in noisy capture of every static asset request.
"""

from enum import Enum
from typing import Dict, FrozenSet, NamedTuple


class ActorResolution(str, Enum):
    """When to read the actor identity for a given event.

    Logout clears the session inside the view handler, so resolving the actor
    AFTER the request would yield None. Login sets the session inside the
    handler, so resolving BEFORE would yield None. Each event picks the side
    of the boundary that carries the correct identity.
    """

    BEFORE_REQUEST = "before"
    AFTER_REQUEST = "after"


class ObservedEvent(NamedTuple):
    event_type: str
    captured_methods: FrozenSet[str]
    captured_status_codes: FrozenSet[int]
    actor_resolution: ActorResolution = ActorResolution.BEFORE_REQUEST


# A 302 from auth.login means a successful authentication and a redirect.
# A 200 means the form re-rendered with errors and the user is not logged in.
_LOGIN_SUCCESS = ObservedEvent(
    "user.login", frozenset({"POST"}), frozenset({302}), ActorResolution.AFTER_REQUEST
)
_LOGOUT = ObservedEvent("user.logout", frozenset({"GET"}), frozenset({302}))
_REGISTER = ObservedEvent(
    "user.register",
    frozenset({"POST"}),
    frozenset({302}),
    ActorResolution.AFTER_REQUEST,
)
_CHALLENGE_VIEW = ObservedEvent(
    "challenge.view", frozenset({"GET"}), frozenset({200})
)
_CHALLENGE_ATTEMPT = ObservedEvent(
    "challenge.attempt", frozenset({"POST"}), frozenset({200})
)
_TEAM_JOIN = ObservedEvent("team.join", frozenset({"POST"}), frozenset({302}))
_TEAM_CREATE = ObservedEvent("team.create", frozenset({"POST"}), frozenset({302}))


ENDPOINT_TO_EVENT: Dict[str, ObservedEvent] = {
    "auth.login": _LOGIN_SUCCESS,
    "auth.logout": _LOGOUT,
    "auth.register": _REGISTER,
    "api.challenges_challenge": _CHALLENGE_VIEW,
    "api.challenges_challenge_attempt": _CHALLENGE_ATTEMPT,
    "teams.join": _TEAM_JOIN,
    "teams.new": _TEAM_CREATE,
}


def lookup(endpoint: str) -> ObservedEvent:
    """Return the ObservedEvent for an endpoint, or raise KeyError."""
    return ENDPOINT_TO_EVENT[endpoint]
