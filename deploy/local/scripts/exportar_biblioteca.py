"""Gera os pacotes da biblioteca de desafios, um por investigação independente.

Um pacote precisa ser autossuficiente: se um desafio depende de outro, os dois
viajam juntos ou o importado nasce inalcançável. A unidade natural de divisão,
portanto, não é a categoria nem a onda, e sim o componente conexo do grafo de
pré-requisitos. Cada componente é uma investigação completa, com sua própria
porta de entrada e suas ramificações.

Uso, de dentro do contêiner do CTFd:

    PYTHONPATH=/opt/CTFd python exportar_biblioteca.py --destino /tmp/biblioteca

Sem --destino o script apenas descreve os pacotes que geraria.
"""

import argparse
import collections
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Set

from CTFd import create_app


def componentes(desafios: Dict[int, object]) -> List[List[int]]:
    """Agrupa os desafios em investigações que não dependem umas das outras."""
    vizinhos = collections.defaultdict(set)
    for desafio in desafios.values():
        for anterior in (desafio.requirements or {}).get("prerequisites") or []:
            if anterior in desafios:
                vizinhos[desafio.id].add(anterior)
                vizinhos[anterior].add(desafio.id)

    visitados: Set[int] = set()
    grupos: List[List[int]] = []
    for identificador in desafios:
        if identificador in visitados:
            continue
        fila, grupo = [identificador], []
        visitados.add(identificador)
        while fila:
            atual = fila.pop()
            grupo.append(atual)
            for vizinho in vizinhos[atual]:
                if vizinho not in visitados:
                    visitados.add(vizinho)
                    fila.append(vizinho)
        grupos.append(sorted(grupo))
    grupos.sort(key=len, reverse=True)
    return grupos


def raizes(grupo: List[int], desafios: Dict[int, object]) -> List[object]:
    """Os desafios do grupo que abrem sem depender de nenhum outro."""
    return [
        desafios[i] for i in grupo if not (desafios[i].requirements or {}).get("prerequisites")
    ]


def chave_do_pacote(nome: str, indice: int) -> str:
    """Deriva uma chave estável do nome da porta de entrada do grupo."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    limpo = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
    return f"{indice:02d}-{limpo}"[:64]


def executar(destino: Path | None) -> None:
    app = create_app()
    with app.app_context():
        from CTFd.models import Challenges
        from CTFd.plugins.hikari_plugin.hikari_challenge_library.exporter import export_library

        desafios = {c.id: c for c in Challenges.query.all()}
        grupos = componentes(desafios)
        print(f"investigações independentes: {len(grupos)}")

        if destino is not None:
            destino.mkdir(parents=True, exist_ok=True)

        for indice, grupo in enumerate(grupos, start=1):
            portas = raizes(grupo, desafios)
            titulo = portas[0].name if portas else desafios[grupo[0]].name
            chave = chave_do_pacote(titulo, indice)
            categorias = collections.Counter(desafios[i].category for i in grupo)
            resumo = ", ".join(f"{nome} x{quantidade}" for nome, quantidade in categorias.most_common(3))
            print(f"  {chave:<38} {len(grupo):>2} desafios | {resumo}")

            if destino is None:
                continue
            pacote = export_library(chave, titulo[:128], challenge_ids=set(grupo))
            caminho = destino / f"{chave}.zip"
            caminho.write_bytes(pacote)
            print(f"      gravado em {caminho} ({len(pacote) // 1024} KB)")


if __name__ == "__main__":
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--destino", type=Path, help="diretório onde gravar os pacotes")
    executar(analisador.parse_args().destino)
