"""Terminal output for the installer.

Separated from the logic so a step never has to decide how it looks, and so the
installer can be driven by something other than a terminal later.
"""

from __future__ import annotations

import sys
from typing import Iterable

from .dto import Finding, Severity


BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

_MARKS = {
    Severity.OK: (GREEN, "ok"),
    Severity.WARNING: (YELLOW, "atenção"),
    Severity.BLOCKER: (RED, "impede"),
}


def uses_colour() -> bool:
    return sys.stdout.isatty()


def paint(text: str, colour: str) -> str:
    return f"{colour}{text}{RESET}" if uses_colour() else text


def heading(text: str) -> None:
    print(f"\n{paint(text, BOLD)}")


def report_finding(finding: Finding) -> None:
    colour, label = _MARKS[finding.severity]
    print(f"  {paint(f'[{label}]', colour)} {finding.subject}: {finding.detail}")
    if finding.remedy:
        print(f"          {paint(finding.remedy, DIM)}")


def report_findings(findings: Iterable[Finding]) -> None:
    for finding in findings:
        report_finding(finding)


def announce(text: str) -> None:
    print(f"  {text}")


def fail(text: str) -> None:
    print(f"\n{paint('ERRO', RED)} {text}", file=sys.stderr)
