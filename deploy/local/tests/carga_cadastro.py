#!/usr/bin/env python3
"""Measures the rush before the whistle: everyone registering at once.

A hundred teams do not arrive gradually. They arrive in the half hour before
the start, all creating accounts and forming teams, and that peak writes to the
database rather than reading from it — the opposite of the load the SIEM test
measures. Accounts are named so the cleanup script recognises them as tests.

    python3 deploy/local/tests/carga_cadastro.py --equipes 100 --por-equipe 3
"""

from __future__ import annotations

import argparse
import asyncio
import re
import time
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


@dataclass
class Medicoes:
    latencias: Dict[str, List[float]] = field(default_factory=dict)
    erros: Dict[str, int] = field(default_factory=dict)

    def registrar(self, etapa: str, segundos: float) -> None:
        self.latencias.setdefault(etapa, []).append(segundos)

    def registrar_erro(self, etapa: str, motivo: str) -> None:
        chave = f"{etapa}: {motivo}"
        self.erros[chave] = self.erros.get(chave, 0) + 1


async def requisitar(host: str, porta: int, metodo: str, caminho: str,
                     cabecalhos: Dict[str, str], corpo: Optional[str] = None
                     ) -> Tuple[int, List[str], str]:
    leitor, escritor = await asyncio.open_connection(host, porta)
    try:
        linhas = [f"{metodo} {caminho} HTTP/1.1", f"Host: {host}", "Connection: close"]
        linhas += [f"{nome}: {valor}" for nome, valor in cabecalhos.items()]
        if corpo is not None:
            linhas.append("Content-Type: application/x-www-form-urlencoded")
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
    jarra = SimpleCookie()
    jarra.load(atuais)
    for linha in cabecalhos:
        if linha.lower().startswith("set-cookie:"):
            jarra.load(linha.split(":", 1)[1].strip())
    return "; ".join(f"{nome}={morsel.value}" for nome, morsel in jarra.items())


def extrair_nonce(pagina: str) -> Optional[str]:
    achado = re.search(r'name="nonce"[^>]*value="([^"]+)"', pagina)
    return achado.group(1) if achado else None


async def com_nonce(host: str, porta: int, caminho: str, cookie: str
                    ) -> Tuple[Optional[str], str]:
    """Fetch a form and return its nonce along with the session it belongs to."""
    _, cabecalhos, corpo = await requisitar(host, porta, "GET", caminho, {"Cookie": cookie})
    return extrair_nonce(corpo), cookies_de(cabecalhos, cookie)


def codificar(campos: Dict[str, str]) -> str:
    from urllib.parse import urlencode
    return urlencode(campos)


def origem(indice: int) -> Dict[str, str]:
    """Present each virtual competitor as its own client.

    CTFd keys its rate limit on the client address, so a test driven from one
    machine measures the limiter instead of the platform. Behind the reverse
    proxy the forwarded address is the real one, which is what a competitor's
    request carries.
    """
    return {"X-Forwarded-For": f"10.{indice // 65536 % 256}.{indice // 256 % 256}.{indice % 256}"}


async def cadastrar(host: str, porta: int, nome: str, senha: str,
                    medicoes: Medicoes, cabecalhos: Dict[str, str]) -> Optional[str]:
    """Create one account and return its session cookie."""
    inicio = time.perf_counter()
    _, resposta, corpo = await requisitar(host, porta, "GET", "/register", dict(cabecalhos))
    nonce, cookie = extrair_nonce(corpo), cookies_de(resposta, "")
    if not nonce:
        medicoes.registrar_erro("cadastro", "formulário sem nonce")
        return None

    dados = codificar({"name": nome, "email": f"{nome}@carga.local",
                       "password": senha, "nonce": nonce})
    codigo, resposta, _ = await requisitar(
        host, porta, "POST", "/register", {**cabecalhos, "Cookie": cookie}, dados)
    if codigo != 302:
        medicoes.registrar_erro("cadastro", f"HTTP {codigo}")
        return None

    medicoes.registrar("cadastro", time.perf_counter() - inicio)
    return cookies_de(resposta, cookie)


async def criar_equipe(host: str, porta: int, cookie: str, nome: str,
                       medicoes: Medicoes, cabecalhos: Dict[str, str]) -> bool:
    inicio = time.perf_counter()
    _, resposta, corpo = await requisitar(
        host, porta, "GET", "/teams/new", {**cabecalhos, "Cookie": cookie})
    nonce, cookie = extrair_nonce(corpo), cookies_de(resposta, cookie)
    if not nonce:
        medicoes.registrar_erro("criar equipe", "formulário sem nonce")
        return False

    dados = codificar({"name": nome, "nonce": nonce})
    codigo, _, _ = await requisitar(
        host, porta, "POST", "/teams/new", {**cabecalhos, "Cookie": cookie}, dados)
    if codigo != 302:
        medicoes.registrar_erro("criar equipe", f"HTTP {codigo}")
        return False

    medicoes.registrar("criar equipe", time.perf_counter() - inicio)
    return True


async def uma_equipe(host: str, porta: int, indice: int, marca: str,
                     por_equipe: int, senha: str, medicoes: Medicoes) -> None:
    """A captain registers, creates the team, and the members register too."""
    cabecalhos = origem(indice * 100)
    capitao = await cadastrar(host, porta, f"cap{indice}_{marca}", senha, medicoes, cabecalhos)
    if capitao is None:
        return
    await criar_equipe(host, porta, capitao, f"equipe{indice}_{marca}", medicoes, cabecalhos)

    membros = [cadastrar(host, porta, f"m{indice}x{n}_{marca}", senha, medicoes,
                         origem(indice * 100 + n))
               for n in range(1, por_equipe)]
    await asyncio.gather(*membros)


def percentil(valores: List[float], fracao: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(int(len(ordenados) * fracao), len(ordenados) - 1)]


def relatar(medicoes: Medicoes, segundos: float) -> int:
    print(f"\n  duração total .............. {segundos:.0f}s")
    for etapa, amostras in medicoes.latencias.items():
        print(f"\n  {etapa}: {len(amostras)} concluído(s)")
        print(f"    mediana .................. {percentil(amostras,0.50)*1000:.0f} ms")
        print(f"    p95 ...................... {percentil(amostras,0.95)*1000:.0f} ms")
        print(f"    pior ..................... {max(amostras)*1000:.0f} ms")
    falhas = sum(medicoes.erros.values())
    print(f"\n  falhas ..................... {falhas}")
    for motivo, quantidade in medicoes.erros.items():
        print(f"    {motivo}: {quantidade}")
    return falhas


async def executar(endereco: str, equipes: int, por_equipe: int,
                   marca: str, senha: str) -> Medicoes:
    partes = urlparse(endereco)
    host, porta = partes.hostname or "127.0.0.1", partes.port or 80
    medicoes = Medicoes()
    await asyncio.gather(*[
        uma_equipe(host, porta, indice, marca, por_equipe, senha, medicoes)
        for indice in range(1, equipes + 1)
    ])
    return medicoes


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga do cadastro e da formação de equipes.")
    parser.add_argument("--endereco", default="http://127.0.0.1:8000")
    parser.add_argument("--equipes", type=int, default=100)
    parser.add_argument("--por-equipe", type=int, default=3)
    parser.add_argument("--senha", default="CargaTeste123")
    argumentos = parser.parse_args()

    # The cleanup script recognises a trailing timestamp as a test account.
    marca = str(int(time.time()))
    pessoas = argumentos.equipes * argumentos.por_equipe
    print(f"Carga de cadastro contra {argumentos.endereco}")
    print(f"  {argumentos.equipes} equipes, {pessoas} pessoas, todas ao mesmo tempo")
    print(f"  marca das contas: _{marca}")

    inicio = time.monotonic()
    medicoes = asyncio.run(executar(argumentos.endereco, argumentos.equipes,
                                    argumentos.por_equipe, marca, argumentos.senha))
    return 1 if relatar(medicoes, time.monotonic() - inicio) else 0


if __name__ == "__main__":
    raise SystemExit(main())
