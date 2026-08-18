"""What competitors will find when the competition opens.

An administrator browsing the challenge grid sees every challenge unlocked,
because CTFd lets an administrator past the prerequisites on purpose. That
makes the grid useless for answering the question asked before every event:
does the game open where it should, and does everything become reachable?
This reads the answer from the challenges themselves.
"""

import json
from typing import Dict, List, Optional

from pydantic import BaseModel

from CTFd.models import Challenges


class CategoryStage(BaseModel):
    """One category as the competitors will meet it."""

    name: str
    total: int
    open_at_start: int
    locked: int


class UnreachableChallenge(BaseModel):
    """A challenge whose prerequisite cannot ever be met."""

    name: str
    category: str
    reason: str


class ChallengeSequence(BaseModel):
    stages: List[CategoryStage]
    unreachable: List[UnreachableChallenge]
    total: int
    open_at_start: int
    # A challenge left hidden reaches nobody, whatever its prerequisites say,
    # and being left hidden by accident is a mistake found during the event.
    hidden: int


def _prerequisites(challenge: Challenges) -> List[int]:
    """Return the challenge ids that have to be solved first."""
    requirements = challenge.requirements
    if not requirements:
        return []
    if isinstance(requirements, str):
        requirements = json.loads(requirements)
    return list(requirements.get("prerequisites") or [])


def _unreachable_reason(prerequisites: List[int], known: Dict[int, Challenges]) -> Optional[str]:
    """Explain why a challenge can never open, or return nothing when it can."""
    missing = [str(identifier) for identifier in prerequisites if identifier not in known]
    if missing:
        return f"depende do desafio {', '.join(missing)}, que não existe"

    hidden = [
        known[identifier].name
        for identifier in prerequisites
        if known[identifier].state != "visible"
    ]
    if hidden:
        return f"depende de {hidden[0]}, que está oculto"
    return None


def build_sequence() -> ChallengeSequence:
    """Describe the order competitors will meet the challenges in."""
    everything = Challenges.query.order_by(Challenges.id).all()
    known = {challenge.id: challenge for challenge in everything}
    challenges = [challenge for challenge in everything if challenge.state == "visible"]

    per_category: Dict[str, CategoryStage] = {}
    unreachable: List[UnreachableChallenge] = []

    for challenge in challenges:
        category = challenge.category or "Sem categoria"
        stage = per_category.setdefault(
            category, CategoryStage(name=category, total=0, open_at_start=0, locked=0)
        )
        stage.total += 1

        prerequisites = _prerequisites(challenge)
        if prerequisites:
            stage.locked += 1
        else:
            stage.open_at_start += 1

        reason = _unreachable_reason(prerequisites, known)
        if reason:
            unreachable.append(
                UnreachableChallenge(name=challenge.name, category=category, reason=reason)
            )

    stages = sorted(per_category.values(), key=lambda stage: stage.name)
    return ChallengeSequence(
        stages=stages,
        unreachable=unreachable,
        total=len(challenges),
        open_at_start=sum(stage.open_at_start for stage in stages),
        hidden=len(everything) - len(challenges),
    )
