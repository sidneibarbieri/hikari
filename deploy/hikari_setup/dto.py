"""Typed values the installer passes between its stages.

Keeping these as models rather than dictionaries means a missing field fails
where it is built, not three stages later where the cause is no longer visible.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """How a finding affects the installation."""

    OK = "ok"
    WARNING = "warning"
    BLOCKER = "blocker"


class Finding(BaseModel):
    """One observation about the host, with the action that resolves it."""

    severity: Severity
    subject: str
    detail: str
    remedy: Optional[str] = None

    @property
    def blocks_installation(self) -> bool:
        return self.severity is Severity.BLOCKER


class HostFacts(BaseModel):
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


class InstallationPlan(BaseModel):
    """Everything the installer needs, resolved before it changes anything."""

    profile: Profile
    repository_root: Path
    compose_files: List[Path]
    project_name: str
    ctfd_port: int = 8000
    domain: Optional[str] = None
    skip_verification: bool = False

    @property
    def local_directory(self) -> Path:
        return self.repository_root / "deploy" / "local"


class StepOutcome(BaseModel):
    """The result of one installation step, for the closing report."""

    name: str
    succeeded: bool
    seconds: float = Field(ge=0)
    message: str = ""
