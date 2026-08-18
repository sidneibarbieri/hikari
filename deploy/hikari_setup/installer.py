"""The installation itself: what runs, in which order, and what it reports."""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Sequence

from . import console
from .dto import InstallationPlan, Profile, StepOutcome
from .runner import compose_invocation, run


READINESS_TIMEOUT_SECONDS = 300
READINESS_INTERVAL_SECONDS = 5


def install(plan: InstallationPlan, compose_command: Sequence[str]) -> List[StepOutcome]:
    """Bring the platform up and configure it, reporting each step as it lands."""
    compose = compose_invocation(plan, compose_command)
    outcomes: List[StepOutcome] = []

    console.heading("Subindo os serviços")
    outcomes.append(_start_services(plan, compose))

    console.heading("Aguardando a plataforma responder")
    outcomes.append(_await_platform(plan))

    console.heading("Configurando a instalação")
    outcomes.extend(_configure(plan))

    return outcomes


def _start_services(plan: InstallationPlan, compose: Sequence[str]) -> StepOutcome:
    outcome = run(
        "subir os serviços",
        list(compose) + ["up", "-d", "--build"],
        plan.local_directory,
        environment=_environment(plan),
    )
    console.announce(f"serviços no ar em {outcome.seconds:.0f}s")
    return outcome


def _await_platform(plan: InstallationPlan) -> StepOutcome:
    """Poll the platform until it answers, so later steps never race the boot."""
    import time

    address = f"http://127.0.0.1:{plan.ctfd_port}/"
    deadline = time.monotonic() + READINESS_TIMEOUT_SECONDS
    started = time.monotonic()

    while time.monotonic() < deadline:
        if _responds(address):
            elapsed = time.monotonic() - started
            console.announce(f"a plataforma respondeu em {elapsed:.0f}s")
            return StepOutcome(name="aguardar a plataforma", succeeded=True, seconds=elapsed)
        time.sleep(READINESS_INTERVAL_SECONDS)

    raise TimeoutError(
        f"A plataforma não respondeu em {address} após {READINESS_TIMEOUT_SECONDS}s.\n"
        "Veja o que aconteceu com: docker compose -p "
        f"{plan.project_name} logs --tail=60 ctfd"
    )


def _responds(address: str) -> bool:
    request = urllib.request.Request(address, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status < 500
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def _configure(plan: InstallationPlan) -> List[StepOutcome]:
    """Apply the configuration every installation needs, in dependency order."""
    scripts = [
        ("preparar o CTFd", "scripts/setup_ctfd.sh"),
        ("garantir a conta administrativa", "scripts/ensure_admin.sh"),
        ("aplicar a identidade visual", "scripts/apply_theme.sh"),
        ("aplicar a página inicial", "scripts/apply_branding.sh"),
        ("configurar o SIEM", "scripts/configure_siem.sh"),
        ("importar os painéis do Kibana", "scripts/import_siem_dashboards.sh"),
    ]

    outcomes = []
    for name, script in scripts:
        outcome = run(name, ["bash", script], plan.local_directory, environment=_environment(plan))
        console.announce(f"{name} ({outcome.seconds:.0f}s)")
        outcomes.append(outcome)
    return outcomes


def _environment(plan: InstallationPlan) -> dict:
    """Pass the plan to the shell steps without leaking it into the caller."""
    environment = dict(os.environ)
    environment["COMPOSE_PROJECT_NAME"] = plan.project_name
    environment["CTFD_PORT"] = str(plan.ctfd_port)
    if plan.profile is Profile.PRODUCTION and plan.domain:
        environment["HIKARI_DOMAIN"] = plan.domain
    return environment
