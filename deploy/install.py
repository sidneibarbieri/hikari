#!/usr/bin/env python3
"""Installs the Hikari platform with one command.

    python3 deploy/install.py                  # development stack
    python3 deploy/install.py --verificar      # only inspects the host
    python3 deploy/install.py --producao DOMINIO

The installer measures the host, says what would stop the installation and what
resolves it, then brings the platform up and configures it. It never repairs
the host silently: an installation that hides the state of the machine leaves
the operator unable to reason about it later.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hikari_setup import console, oauth, preflight  # noqa: E402
from hikari_setup.dto import InstallationPlan, Profile, Severity  # noqa: E402
from hikari_setup.installer import install  # noqa: E402
from hikari_setup.runner import StepFailed  # noqa: E402


def build_plan(arguments: argparse.Namespace) -> InstallationPlan:
    repository_root = Path(__file__).resolve().parents[1]
    local = repository_root / "deploy" / "local"

    if arguments.producao:
        return InstallationPlan(
            profile=Profile.PRODUCTION,
            repository_root=repository_root,
            compose_files=[
                local / "docker-compose.yml",
                repository_root / "deploy" / "production" / "docker-compose.production.yml",
            ],
            project_name="hikari",
            ctfd_port=arguments.porta,
            domain=arguments.producao,
        )

    return InstallationPlan(
        profile=Profile.DEVELOPMENT,
        repository_root=repository_root,
        compose_files=[local / "docker-compose.yml"],
        project_name="local",
        ctfd_port=arguments.porta,
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Instala a plataforma Hikari.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--producao",
        metavar="DOMINIO",
        help="instala o perfil de produção para o domínio informado",
    )
    parser.add_argument(
        "--verificar",
        action="store_true",
        help="apenas inspeciona a máquina, sem instalar nada",
    )
    parser.add_argument("--porta", type=int, default=8000, help="porta do CTFd (padrão: 8000)")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    plan = build_plan(arguments)

    console.heading(f"Hikari — instalação ({plan.profile.value})")

    facts = preflight.describe_host(plan.local_directory)
    console.announce(
        f"{facts.operating_system} · {facts.cpu_count} vCPU · {facts.memory_gib:.1f} GiB"
    )

    console.heading("Verificando a máquina")
    findings = preflight.inspect(facts, plan.ctfd_port) + [oauth.describe(plan)]
    console.report_findings(findings)

    blockers = [finding for finding in findings if finding.blocks_installation]
    if blockers:
        console.fail(
            f"{len(blockers)} item(ns) impedem a instalação. "
            "Resolva o que está indicado acima e execute novamente."
        )
        return 1

    if arguments.verificar:
        console.heading("A máquina está pronta para instalar.")
        return 0

    if facts.compose_command is None:
        console.fail("Docker Compose não encontrado.")
        return 1

    outcomes = install(plan, facts.compose_command)

    console.heading("Instalação concluída")
    total_seconds = sum(outcome.seconds for outcome in outcomes)
    console.announce(f"{len(outcomes)} passos em {total_seconds:.0f}s")
    console.announce(f"Acesse: http://localhost:{plan.ctfd_port}")
    if oauth.credentials_present():
        console.announce(
            "Registre no Google Cloud Console o URI: " + oauth.redirect_uri(plan)
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except StepFailed as failure:
        console.fail(str(failure))
        sys.exit(1)
    except (RuntimeError, TimeoutError) as failure:
        console.fail(str(failure))
        sys.exit(1)
