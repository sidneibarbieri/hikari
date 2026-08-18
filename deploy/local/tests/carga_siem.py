#!/usr/bin/env python3
"""Measures the authenticated SIEM path, which costs the most per request.

Every competitor spends the competition querying Kibana through the Hikari
proxy, so this is the path that decides whether an event holds up. The public
surfaces are covered by carga.py; this one signs in first and then behaves like
someone hunting through the logs.

    python3 deploy/local/tests/carga_siem.py --contas 10 --por-conta 20 --segundos 60
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import Dict, List, Optional
from urllib.parse import urlparse


CONSULTAS = [
    "event.dataset:appdb",
    "event.dataset:auth AND event.outcome:failure",
    "event.dataset:firewall",
    "event.dataset:dns",
    "event.dataset:edr",
]


@dataclass
class Medicoes:
    latencias: Dict[str, List[float]] = field(default_factory=dict)
    erros: Dict[str, int] = field(default_factory=dict)

    def registrar(self, etapa: str, segundos: float) -> None:
        self.latencias.setdefault(etapa, []).append(segundos)

    def registrar_erro(self, motivo: str) -> None:
        self.erros[motivo] = self.erros.get(motivo, 0) + 1


async def requisitar(host: str, porta: int, metodo: str, caminho: str,
                     cabecalhos: Dict[str, str], corpo: Optional[str] = None):
    """Send one request and return status, headers and body."""
    leitor, escritor = await asyncio.open_connection(host, porta)
    try:
        linhas = [f"{metodo} {caminho} HTTP/1.1", f"Host: {host}", "Connection: close"]
        linhas += [f"{nome}: {valor}" for nome, valor in cabecalhos.items()]
        if corpo is not None:
            linhas.append(f"Content-Length: {len(corpo.encode())}")
        pedido = "\r\n".join(linhas) + "\r\n\r\n" + (corpo or "")
        escritor.write(pedido.encode())
        await escritor.drain()

        cabecalho_bruto = await leitor.readuntil(b"\r\n\r\n")
        corpo_bruto = await leitor.read()
        primeira, *resto = cabecalho_bruto.decode(errors="replace").split("\r\n")
        return int(primeira.split()[1]), resto, corpo_bruto.decode(errors="replace")
    finally:
        escritor.close()
        await escritor.wait_closed()


def cookies_de(cabecalhos: List[str], atuais: str) -> str:
    """Merge Set-Cookie headers into the cookie string sent back."""
    jarra = SimpleCookie()
    jarra.load(atuais)
    for linha in cabecalhos:
        if linha.lower().startswith("set-cookie:"):
            jarra.load(linha.split(":", 1)[1].strip())
    return "; ".join(f"{nome}={morsel.value}" for nome, morsel in jarra.items())


async def autenticar(host: str, porta: int, usuario: str, senha: str) -> Optional[str]:
    """Sign in and return the session cookie, or None when it fails."""
    codigo, cabecalhos, corpo = await requisitar(host, porta, "GET", "/login", {})
    cookie = cookies_de(cabecalhos, "")
    achado = re.search(r'name="nonce"[^>]*value="([^"]+)"', corpo)
    if not achado:
        return None

    dados = f"name={usuario}&password={senha}&nonce={achado.group(1)}"
    codigo, cabecalhos, _ = await requisitar(
        host, porta, "POST", "/login",
        {"Cookie": cookie, "Content-Type": "application/x-www-form-urlencoded"},
        dados,
    )
    return cookies_de(cabecalhos, cookie) if codigo == 302 else None


async def um_investigador(host: str, porta: int, cookie: str, fim: float,
                          medicoes: Medicoes, indice: int) -> None:
    """Behave like one competitor hunting through the SIEM until time runs out."""
    passo = indice
    while time.monotonic() < fim:
        consulta = CONSULTAS[passo % len(CONSULTAS)]
        passo += 1
        corpo = json.dumps({"params": {"index": "competition1", "body": {
            "size": 5, "query": {"query_string": {"query": consulta}}}}})
        inicio = time.perf_counter()
        try:
            codigo, _, _ = await requisitar(
                host, porta, "POST", "/hikari/kibana/internal/search/ese",
                {"Cookie": cookie, "Content-Type": "application/json", "kbn-xsrf": "true"},
                corpo,
            )
            if codigo >= 400:
                medicoes.registrar_erro(f"HTTP {codigo}")
            else:
                medicoes.registrar("consulta ao SIEM", time.perf_counter() - inicio)
        except (ConnectionError, OSError, asyncio.IncompleteReadError) as falha:
            medicoes.registrar_erro(type(falha).__name__)
        await asyncio.sleep(1.0)   # a person reads the results


def percentil(valores: List[float], fracao: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(int(len(ordenados) * fracao), len(ordenados) - 1)]


def relatar(medicoes: Medicoes, investigadores: int, segundos: float) -> None:
    print(f"\n  investigadores simultâneos . {investigadores}")
    print(f"  duração .................... {segundos:.0f}s")
    falhas = sum(medicoes.erros.values())
    for etapa, amostras in medicoes.latencias.items():
        print(f"\n  {etapa}: {len(amostras)} respostas "
              f"({len(amostras)/segundos:.1f}/s)")
        print(f"    mediana .................. {percentil(amostras,0.50)*1000:.0f} ms")
        print(f"    p95 ...................... {percentil(amostras,0.95)*1000:.0f} ms")
        print(f"    p99 ...................... {percentil(amostras,0.99)*1000:.0f} ms")
        print(f"    pior ..................... {max(amostras)*1000:.0f} ms")
    print(f"\n  falhas ..................... {falhas}"
          + (f"  {medicoes.erros}" if falhas else ""))


async def executar(endereco: str, contas: List[str], senha: str,
                   por_conta: int, segundos: int) -> Medicoes:
    partes = urlparse(endereco)
    host, porta = partes.hostname or "127.0.0.1", partes.port or 80

    sessoes = await asyncio.gather(*[autenticar(host, porta, c, senha) for c in contas])
    validas = [s for s in sessoes if s]
    if not validas:
        raise RuntimeError("Nenhuma conta autenticou. Confira usuário e senha.")
    print(f"  sessões autenticadas: {len(validas)} de {len(contas)}")

    medicoes = Medicoes()
    fim = time.monotonic() + segundos
    tarefas = [um_investigador(host, porta, validas[i % len(validas)], fim, medicoes, i)
               for i in range(len(validas) * por_conta)]
    await asyncio.gather(*tarefas)
    return medicoes


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga sobre o proxy autenticado do SIEM.")
    parser.add_argument("--endereco", default="http://127.0.0.1:8000")
    parser.add_argument("--prefixo", required=True, help="prefixo das contas de teste")
    parser.add_argument("--contas", type=int, default=10)
    parser.add_argument("--senha", default="CargaTeste123")
    parser.add_argument("--por-conta", type=int, default=10,
                        help="sessões simultâneas por conta")
    parser.add_argument("--segundos", type=int, default=60)
    argumentos = parser.parse_args()

    contas = [f"{argumentos.prefixo}{i}" for i in range(1, argumentos.contas + 1)]
    print(f"Carga no SIEM contra {argumentos.endereco}")
    inicio = time.monotonic()
    medicoes = asyncio.run(executar(argumentos.endereco, contas, argumentos.senha,
                                    argumentos.por_conta, argumentos.segundos))
    relatar(medicoes, len(contas) * argumentos.por_conta, time.monotonic() - inicio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
