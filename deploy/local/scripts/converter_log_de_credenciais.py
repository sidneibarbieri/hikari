"""Rebuilds the credential export log into the schema the SIEM indexes.

The file arrived as a JSON array whose objects carry fragments of a log line as
keys, the result of splitting plain text on commas. The original lines are
recoverable: the values of each object, joined back with commas, are one line.

The fields written here are deliberately narrow. Challenges already in play
count event.action, event.severity, host.mac and user.name across the whole
index, so a hundred thousand new records carrying any of those would change
answers that are already correct. This log answers a different question and
keeps to its own fields.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterator, List

from pydantic import BaseModel

LINHA = re.compile(
    r"^(?P<carimbo>\S+ \S+) \[(?P<thread>[^\]]+)\] (?P<nivel>\w+) (?P<origem>\S+)\s+- "
    r"\[req:(?P<requisicao>[^\]]+)\] ClientIP: (?P<endereco>\S+) \| .*?"
    r'"email":"(?P<email>[^"]+)".*?"pwd_hash":"(?P<segredo>[^"]*)".*?"status":"(?P<estado>[^"]*)"'
)

CONJUNTO = "credenciais"


CABECALHO = re.compile(r"^(?P<carimbo>\S+ \S+) \[[^\]]+\] \w+\s+\S+")


class RegistroDeCredencial(BaseModel):
    """One exported account, as the SIEM will hold it."""

    carimbo: str
    endereco: str
    email: str
    segredo: str
    estado: str
    requisicao: str
    mensagem: str

    def para_evento(self) -> Dict[str, object]:
        """Return the document, using field names no other challenge counts."""
        return {
            "@timestamp": self.carimbo.replace(" ", "T") + "-03:00",
            "event.dataset": CONJUNTO,
            "event.id": self.requisicao,
            "source.ip": self.endereco,
            "user.email": self.email,
            "credential.hash": self.segredo,
            "credential.status": self.estado,
            "message": self.mensagem,
        }


def linhas_do_arquivo(caminho: Path) -> Iterator[str]:
    """Recover one log line per object in the malformed export.

    The first line of the original text became the keys of every object, so it
    survives only there. Reading it once from the first object recovers the
    account that would otherwise be missing from the haystack.
    """
    objetos: List[Dict[str, str]] = json.loads(caminho.read_text(encoding="utf-8"))
    if objetos:
        yield ", ".join(objetos[0].keys()).replace('\\"', '"')
    for objeto in objetos:
        yield ", ".join(objeto.values()).replace('\\"', '"')


def evento_narrativo(linha: str) -> Dict[str, object]:
    """Carry a line that is not an account export, keeping only what it has.

    A dozen lines describe the operation around the export: a slow query, a
    failed login. They belong in the haystack as text, and inventing account
    fields for them would be inventing evidence.
    """
    achado = CABECALHO.match(linha)
    if achado is None:
        raise ValueError(f"linha sem carimbo de tempo: {linha[:120]}")
    return {
        "@timestamp": achado.group("carimbo").replace(" ", "T") + "-03:00",
        "event.dataset": CONJUNTO,
        "message": linha,
    }


def eventos_do_arquivo(caminho: Path) -> Iterator[Dict[str, object]]:
    """Yield one document per line, structured when the line is an export."""
    for linha in linhas_do_arquivo(caminho):
        # Splitting the original text on commas left trailing empty fragments,
        # which rejoin into a line of nothing but separators.
        if not linha.strip(" ,"):
            continue
        achado = LINHA.match(linha)
        if achado is None:
            yield evento_narrativo(linha)
            continue
        yield RegistroDeCredencial(mensagem=linha, **achado.groupdict()).para_evento()


def main() -> int:
    parser = argparse.ArgumentParser(description="Converte o log de credenciais para o esquema do SIEM.")
    parser.add_argument("origem", type=Path)
    parser.add_argument("destino", type=Path)
    argumentos = parser.parse_args()

    eventos = list(eventos_do_arquivo(argumentos.origem))
    argumentos.destino.write_text(
        json.dumps({"eventos": eventos}, ensure_ascii=False), encoding="utf-8"
    )
    contas = {evento["user.email"] for evento in eventos if "user.email" in evento}
    narrativos = sum(1 for evento in eventos if "user.email" not in evento)
    print(f"  eventos convertidos .: {len(eventos)}")
    print(f"  contas distintas ....: {len(contas)}")
    print(f"  linhas narrativas ...: {narrativos}")
    print(f"  campos do primeiro ..: {', '.join(eventos[0].keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
