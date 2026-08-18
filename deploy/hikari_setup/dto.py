"""Typed values the installer passes between its stages.

These use the standard library alone. The installer is the one component that
runs before anything is prepared, on a host where no dependency can be assumed,
so requiring a package to install packages would defeat its purpose. The
application itself, which runs inside the container, uses Pydantic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class Severity(str, Enum):
    """How a finding affects the installation."""

    OK = "ok"
    WARNING = "warning"
    BLOCKER = "blocker"


@dataclass(frozen=True)
class Finding:
    """One observation about the host, with the action that resolves it."""

    severity: Severity
    subject: str
    detail: str
    remedy: Optional[str] = None

    @property
    def blocks_installation(self) -> bool:
        return self.severity is Severity.BLOCKER


@dataclass(frozen=True)
class HostFacts:
    """What the installer measured about the machine it runs on."""

    operating_system: str
    memory_gib: float
    free_disk_gib: float
    cpu_count: int
    docker_version: Optional[str] = None
    compose_command: Optional[List[str]] = None
    docker_memory_gib: Optional[float] = None


class Profile(str, Enum):
    """Which installation is being prepared."""

    DEVELOPMENT = "desenvolvimento"
    PRODUCTION = "producao"


@dataclass(frozen=True)
class InstallationPlan:
    """Everything the installer needs, resolved before it changes anything."""

    profile: Profile
    repository_root: Path
    compose_files: List[Path] = field(default_factory=list)
    project_name: str = "local"
    ctfd_port: int = 8000
    domain: Optional[str] = None

    def __post_init__(self) -> None:
        if self.profile is Profile.PRODUCTION and not self.domain:
            raise ValueError("O perfil de produção exige um domínio.")
        if not 1 <= self.ctfd_port <= 65535:
            raise ValueError(f"Porta fora do intervalo válido: {self.ctfd_port}")

    @property
    def local_directory(self) -> Path:
        return self.repository_root / "deploy" / "local"


@dataclass(frozen=True)
class StepOutcome:
    """The result of one installation step, for the closing report."""

    name: str
    succeeded: bool
    seconds: float
    message: str = ""
