"""Runs the commands the installation is made of.

A failing command stops the installation with its own output attached. Nothing
here converts a failure into a warning: the operator has to see what broke, in
the words of the tool that broke.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import List, Optional, Sequence

from .dto import InstallationPlan, StepOutcome


class StepFailed(RuntimeError):
    """A command that the installation depends on returned a failure."""

    def __init__(self, name: str, command: Sequence[str], output: str) -> None:
        super().__init__(f"{name} falhou\n\n$ {' '.join(command)}\n\n{output.strip()}")
        self.step_name = name


def compose_invocation(plan: InstallationPlan, compose_command: Sequence[str]) -> List[str]:
    """Build the Compose prefix for this plan, including every file it needs."""
    invocation = list(compose_command) + ["-p", plan.project_name]
    for compose_file in plan.compose_files:
        invocation += ["-f", str(compose_file)]
    return invocation


def run(
    name: str,
    command: Sequence[str],
    working_directory: Path,
    environment: Optional[dict] = None,
    timeout_seconds: int = 1800,
) -> StepOutcome:
    """Run one command, letting its failure carry its own explanation."""
    started = time.monotonic()
    completed = subprocess.run(
        list(command),
        cwd=working_directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    elapsed = time.monotonic() - started

    if completed.returncode != 0:
        raise StepFailed(name, command, completed.stdout + completed.stderr)

    return StepOutcome(name=name, succeeded=True, seconds=elapsed)
