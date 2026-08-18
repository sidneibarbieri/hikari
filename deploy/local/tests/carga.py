#!/usr/bin/env python3
"""Measures how the platform answers while many people use it at once.

Run it on the machine that hosts the platform, against the loopback address:
the question is what the platform can serve, and a test driven from a laptop
would measure the network between the laptop and the server instead.

    python3 deploy/local/tests/carga.py --usuarios 300 --segundos 60

It reports the distribution of response times rather than an average, because
an average hides the slow tail that competitors actually notice.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from urllib.parse import urlparse


# The paths a competitor loads while playing, with the weight of each in a
# realistic mix: the board is polled, the guide is read once.
PERCURSO = [
    ("/", 2),
    ("/hikari/live", 3),
    ("/hikari/live/data", 4),
    ("/hikari/guide", 1),
]


@dataclass
class Medicoes:
    """Latencies and failures collected during one run."""

    latencias: List[float] = field(default_factory=list)
    por_caminho: Dict[str, List[float]] = field(default_factory=dict)
    erros: Dict[str, int] = field(default_factory=dict)

    def registrar(self, caminho: str, segundos: float) -> None:
        self.latencias.append(segundos)
        self.por_caminho.setdefault(caminho, []).append(segundos)

    def registrar_erro(self, motivo: str) -> None:
        self.erros[motivo] = self.erros.get(motivo, 0) + 1


async def uma_requisicao(host: str, porta: int, caminho: str, medicoes: Medicoes) -> None:
    """Issue one request and record how long the answer took."""
    inicio = time.perf_counter()
    leitor, escritor = await asyncio.open_connection(host, porta)
    try:
        pedido = (
            f"GET {caminho} HTTP/1.1\r\nHost: {host}\r\n"
            "User-Agent: hikari-carga\r\nConnection: close\r\n\r\n"
        )
        escritor.write(pedido.encode())
        await escritor.drain()

        primeira_linha = await leitor.readline()
        if not primeira_linha:
            medicoes.registrar_erro("resposta vazia")
            return
        codigo = primeira_linha.split()[1].decode()
        await leitor.read()

        if codigo.startswith(("4", "5")):
            medicoes.registrar_erro(f"HTTP {codigo}")
            return
        medicoes.registrar(caminho, time.perf_counter() - inicio)
    finally:
        escritor.close()
        await escritor.wait_closed()


async def um_competidor(host: str, porta: int, fim: float, medicoes: Medicoes) -> None:
    """Behave like one person browsing until the run is over."""
    percurso = [caminho for caminho, peso in PERCURSO for _ in range(peso)]
    indice = 0
    while time.monotonic() < fim:
        caminho = percurso[indice % len(percurso)]
        indice += 1
        try:
            await uma_requisicao(host, porta, caminho, medicoes)
        except (ConnectionError, OSError, asyncio.TimeoutError) as falha:
            medicoes.registrar_erro(type(falha).__name__)
        await asyncio.sleep(0.5)   # a person reads between clicks


def percentil(valores: List[float], fracao: float) -> float:
    ordenados = sorted(valores)
    posicao = min(int(len(ordenados) * fracao), len(ordenados) - 1)
    return ordenados[posicao]


def relatar(medicoes: Medicoes, usuarios: int, segundos: float) -> None:
    total = len(medicoes.latencias)
    falhas = sum(medicoes.erros.values())

    print(f"\n  usuários simultâneos ....... {usuarios}")
    print(f"  duração .................... {segundos:.0f}s")
    print(f"  respostas bem-sucedidas .... {total}")
    print(f"  requisições por segundo .... {total / segundos:.1f}")
    print(f"  falhas ..................... {falhas}"
          + (f"  {medicoes.erros}" if falhas else ""))

    if not total:
        return

    print(f"\n  tempo de resposta (ms)")
    print(f"    mediana .................. {percentil(medicoes.latencias, 0.50)*1000:.0f}")
    print(f"    p95 ...................... {percentil(medicoes.latencias, 0.95)*1000:.0f}")
    print(f"    p99 ...................... {percentil(medicoes.latencias, 0.99)*1000:.0f}")
    print(f"    pior .................... {max(medicoes.latencias)*1000:.0f}")

    print(f"\n  por caminho (mediana / p95, ms)")
    for caminho, amostras in sorted(medicoes.por_caminho.items()):
        print(f"    {caminho:<22} {percentil(amostras,0.50)*1000:>6.0f} / "
              f"{percentil(amostras,0.95)*1000:>6.0f}   ({len(amostras)} amostras)")


async def executar(endereco: str, usuarios: int, segundos: int) -> Medicoes:
    partes = urlparse(endereco)
    host = partes.hostname or "127.0.0.1"
    porta = partes.port or 80

    medicoes = Medicoes()
    fim = time.monotonic() + segundos
    await asyncio.gather(*[um_competidor(host, porta, fim, medicoes) for _ in range(usuarios)])
    return medicoes


def main() -> int:
    parser = argparse.ArgumentParser(description="Teste de carga da plataforma Hikari.")
    parser.add_argument("--endereco", default="http://127.0.0.1:8000")
    parser.add_argument("--usuarios", type=int, default=100)
    parser.add_argument("--segundos", type=int, default=60)
    argumentos = parser.parse_args()

    print(f"Carga contra {argumentos.endereco}")
    inicio = time.monotonic()
    medicoes = asyncio.run(executar(argumentos.endereco, argumentos.usuarios, argumentos.segundos))
    relatar(medicoes, argumentos.usuarios, time.monotonic() - inicio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
