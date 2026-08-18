"""Checks the host before anything is installed.

Every check answers one question and, when the answer is bad, says what to do
about it. A check never fixes anything: an installer that silently repairs the
host hides the state the operator will have to reason about later.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path
from typing import List, Optional

from .dto import Finding, HostFacts, Severity


MINIMUM_MEMORY_GIB = 8.0
MINIMUM_DISK_GIB = 10.0
MINIMUM_DOCKER_MEMORY_GIB = 8.0


def describe_host(target_directory: Path) -> HostFacts:
    """Measure the machine. Raises if the platform is one we never support."""
    system = platform.system()
    if system not in ("Linux", "Darwin"):
        raise RuntimeError(f"Sistema operacional não suportado: {system}")

    usage = shutil.disk_usage(target_directory)
    return HostFacts(
        operating_system=_operating_system_name(system),
        memory_gib=_physical_memory_gib(system),
        free_disk_gib=usage.free / 1024**3,
        cpu_count=os.cpu_count() or 1,
        docker_version=_docker_version(),
        compose_command=find_compose_command(),
        docker_memory_gib=_docker_memory_gib(),
    )


def _operating_system_name(system: str) -> str:
    if system == "Darwin":
        release = subprocess.run(
            ["sw_vers", "-productVersion"], capture_output=True, text=True, check=False
        ).stdout.strip()
        return f"macOS {release}".strip()

    release_file = Path("/etc/os-release")
    if release_file.exists():
        for line in release_file.read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    return "Linux"


def _physical_memory_gib(system: str) -> float:
    if system == "Darwin":
        raw = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=True
        ).stdout
        return int(raw) / 1024**3

    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) / 1024**2
    raise RuntimeError("MemTotal ausente em /proc/meminfo")


def _docker_version() -> Optional[str]:
    if shutil.which("docker") is None:
        return None
    result = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or None


def _docker_memory_gib() -> Optional[float]:
    """Read the memory the Docker engine can actually use.

    On macOS and Windows this is a virtual machine sized independently of the
    host, and it is routinely smaller than the documented minimum.
    """
    if shutil.which("docker") is None:
        return None
    result = subprocess.run(
        ["docker", "info", "--format", "{{json .MemTotal}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return json.loads(result.stdout) / 1024**3


def find_compose_command() -> Optional[List[str]]:
    """Return the Compose invocation this host supports."""
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    if shutil.which("docker"):
        probe = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, check=False
        )
        if probe.returncode == 0:
            return ["docker", "compose"]
    return None


def inspect(facts: HostFacts, ctfd_port: int) -> List[Finding]:
    """Turn the measurements into findings the operator can act on."""
    return [
        _check_docker(facts),
        _check_compose(facts),
        _check_host_memory(facts),
        _check_docker_memory(facts),
        _check_disk(facts),
        _check_port(ctfd_port),
    ]


def _check_docker(facts: HostFacts) -> Finding:
    if facts.docker_version:
        return Finding(
            severity=Severity.OK, subject="Docker", detail=f"versão {facts.docker_version}"
        )
    return Finding(
        severity=Severity.BLOCKER,
        subject="Docker",
        detail="não encontrado ou o serviço não está no ar",
        remedy="Instale o Docker Engine 24+ e confirme com: docker version",
    )


def _check_compose(facts: HostFacts) -> Finding:
    if facts.compose_command:
        return Finding(
            severity=Severity.OK,
            subject="Docker Compose",
            detail=" ".join(facts.compose_command),
        )
    return Finding(
        severity=Severity.BLOCKER,
        subject="Docker Compose",
        detail="nem o plugin nem o docker-compose foram encontrados",
        remedy="Instale o plugin Compose v2: https://docs.docker.com/compose/install/",
    )


def _check_host_memory(facts: HostFacts) -> Finding:
    detail = f"{facts.memory_gib:.1f} GiB na máquina"
    if facts.memory_gib >= MINIMUM_MEMORY_GIB:
        return Finding(severity=Severity.OK, subject="Memória", detail=detail)
    return Finding(
        severity=Severity.WARNING,
        subject="Memória",
        detail=f"{detail}, abaixo dos {MINIMUM_MEMORY_GIB:.0f} GiB recomendados",
        remedy="A plataforma sobe, mas o Elasticsearch pode ficar lento sob carga",
    )


def _check_docker_memory(facts: HostFacts) -> Finding:
    if facts.docker_memory_gib is None:
        return Finding(
            severity=Severity.WARNING,
            subject="Memória do Docker",
            detail="não foi possível medir",
            remedy="Confirme que o serviço do Docker está no ar",
        )

    detail = f"{facts.docker_memory_gib:.1f} GiB disponíveis ao Docker"
    if facts.docker_memory_gib >= MINIMUM_DOCKER_MEMORY_GIB:
        return Finding(severity=Severity.OK, subject="Memória do Docker", detail=detail)
    return Finding(
        severity=Severity.WARNING,
        subject="Memória do Docker",
        detail=f"{detail}, abaixo dos {MINIMUM_DOCKER_MEMORY_GIB:.0f} GiB recomendados",
        remedy="No macOS: colima stop && colima start --memory 16 --disk 60 --cpu 4",
    )


def _check_disk(facts: HostFacts) -> Finding:
    detail = f"{facts.free_disk_gib:.1f} GiB livres"
    if facts.free_disk_gib >= MINIMUM_DISK_GIB:
        return Finding(severity=Severity.OK, subject="Disco", detail=detail)
    return Finding(
        severity=Severity.BLOCKER,
        subject="Disco",
        detail=f"{detail}, abaixo dos {MINIMUM_DISK_GIB:.0f} GiB necessários",
        remedy="Libere espaço com: docker system prune -a",
    )


def _check_port(port: int) -> Finding:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1.0)
        in_use = probe.connect_ex(("127.0.0.1", port)) == 0

    if not in_use:
        return Finding(severity=Severity.OK, subject=f"Porta {port}", detail="livre")
    return Finding(
        severity=Severity.WARNING,
        subject=f"Porta {port}",
        detail="já está em uso",
        remedy=(
            "Se for uma instalação anterior do Hikari, siga adiante. "
            f"Caso contrário, pare o serviço ou defina CTFD_PORT"
        ),
    )
