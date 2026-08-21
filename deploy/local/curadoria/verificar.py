"""Resolve cada desafio curado contra o índice e compara com a flag cadastrada.

A conferência faz o que o competidor faria: filtra o conjunto de eventos,
agrega pelo campo em questão e lê o resultado. Nenhum desafio é aprovado por
inspeção do enunciado; todos são aprovados por consulta.

Uso:

    python verificar.py [--indice leonardo] [--container local-elasticsearch-1]
"""

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from conferencias import CONFERENCIAS
from plantao_soc import INVESTIGACOES, TRILHA_DE_ENDPOINT


class Consulta:
    """Uma conexão de leitura ao índice de eventos."""

    def __init__(self, container: str, indice: str) -> None:
        self.container = container
        self.indice = indice

    def buscar(self, corpo: Dict) -> Dict:
        resultado = subprocess.run(
            ["docker", "exec", "-i", self.container, "curl", "-s", "-X", "POST",
             f"localhost:9200/{self.indice}/_search",
             "-H", "Content-Type: application/json", "-d", "@-"],
            input=json.dumps(corpo).encode(), capture_output=True,
        )
        return json.loads(resultado.stdout)


def normalizar(texto: str) -> str:
    return unicodedata.normalize("NFC", texto)


def filtros_de(conferencia: Dict) -> List[Dict]:
    filtros: List[Dict] = []
    if "conjunto" in conferencia:
        filtros.append({"term": {"event.dataset.keyword": normalizar(conferencia["conjunto"])}})
    if "conjuntos" in conferencia:
        filtros.append({"terms": {"event.dataset.keyword": [normalizar(c) for c in conferencia["conjuntos"]]}})
    for campo, valor in (conferencia.get("filtro") or {}).items():
        filtros.append({"term": {campo: valor}})
    return filtros


def valores(consulta: Consulta, conferencia: Dict, tamanho: int = 20) -> List[Tuple[str, int]]:
    resposta = consulta.buscar({
        "size": 0,
        "query": {"bool": {"filter": filtros_de(conferencia)}},
        "aggs": {"v": {"terms": {"field": conferencia["campo"], "size": tamanho}}},
    })
    baldes = resposta.get("aggregations", {}).get("v", {}).get("buckets", [])
    return [(str(b["key"]), b["doc_count"]) for b in baldes]


def resolver(consulta: Consulta, chave: str, flag: str) -> Tuple[bool, str]:
    """Executa a investigação e diz se ela produz a flag."""
    conferencia = CONFERENCIAS.get(chave)
    if conferencia is None:
        return False, "sem conferência declarada"
    modo = conferencia["modo"]

    if modo == "contagem":
        total = consulta.buscar({"size": 0, "query": {"bool": {"filter": filtros_de(conferencia)}}})
        obtido = str(total["hits"]["total"]["value"])
        return obtido == flag, f"contagem = {obtido}"

    if modo == "cardinalidade":
        resposta = consulta.buscar({
            "size": 0, "query": {"bool": {"filter": filtros_de(conferencia)}},
            "aggs": {"d": {"cardinality": {"field": conferencia["campo"], "precision_threshold": 40000}}},
        })
        obtido = str(resposta["aggregations"]["d"]["value"])
        return obtido == flag, f"valores distintos = {obtido}"

    if modo == "texto":
        resposta = consulta.buscar({
            "size": 1, "query": {"bool": {"filter": filtros_de(conferencia)}},
            "_source": [conferencia["campo"]],
        })
        acertos = resposta["hits"]["hits"]
        if not acertos:
            return False, "nenhum evento"
        texto = str(acertos[0]["_source"].get(conferencia["campo"], ""))
        return flag in texto, f"texto: {texto[:70]}"

    if modo == "primeiro":
        resposta = consulta.buscar({
            "size": 1, "query": {"bool": {"filter": filtros_de(conferencia)}},
            "sort": [{"@timestamp": "asc"}], "_source": [conferencia["campo"]],
        })
        acertos = resposta["hits"]["hits"]
        if not acertos:
            return False, "nenhum evento"
        obtido = str(acertos[0]["_source"].get(conferencia["campo"], ""))
        return obtido == flag, f"primeiro = {obtido}"

    encontrados = valores(consulta, conferencia)
    if not encontrados:
        return False, "campo vazio no conjunto"

    if modo == "unico":
        distintos = {v for v, _ in encontrados}
        ok = distintos == {flag}
        return ok, f"{len(distintos)} valor(es): {', '.join(sorted(distintos)[:3])[:60]}"

    if modo == "entre_os_valores":
        distintos = [v for v, _ in encontrados]
        return flag in distintos, f"valores: {', '.join(distintos[:4])[:70]}"

    if modo == "sufixo":
        candidatos = [v for v, _ in encontrados if v.rsplit("\\", 1)[-1] == flag]
        return bool(candidatos), f"campo traz o caminho completo: {candidatos[0] if candidatos else encontrados[0][0]}"

    if modo == "topo":
        primeiro, contagem = encontrados[0]
        segundo = encontrados[1][1] if len(encontrados) > 1 else 0
        return primeiro == flag, f"topo {primeiro} ({contagem}) contra {segundo}"

    if modo == "topo_sem_caixa":
        agregado = Counter()
        for valor, contagem in encontrados:
            agregado[valor.lower()] += contagem
        primeiro, contagem = agregado.most_common(1)[0]
        return primeiro == flag.lower(), f"topo sem caixa {primeiro} ({contagem})"

    if modo == "soma_sem_caixa":
        alvo = conferencia["valor"].lower()
        soma = sum(c for v, c in encontrados if v.lower() == alvo)
        return str(soma) == flag, f"soma sem caixa = {soma}"

    if modo == "comum_aos_conjuntos":
        resposta = consulta.buscar({
            "size": 0, "query": {"bool": {"filter": filtros_de(conferencia)}},
            "aggs": {"v": {"terms": {"field": conferencia["campo"], "size": 20},
                           "aggs": {"c": {"cardinality": {"field": "event.dataset.keyword"}}}}},
        })
        comuns = [
            b["key"] for b in resposta["aggregations"]["v"]["buckets"]
            if b["c"]["value"] == len(conferencia["conjuntos"])
        ]
        return comuns == [flag], f"identidades nos dois conjuntos: {comuns}"

    return False, f"modo desconhecido: {modo}"


def desafios_curados() -> List[Dict]:
    saida = []
    for bloco in INVESTIGACOES + [TRILHA_DE_ENDPOINT]:
        for desafio in bloco["desafios"]:
            saida.append({**desafio, "investigacao": bloco["titulo"]})
    return saida


def executar(container: str, indice: str) -> None:
    consulta = Consulta(container, indice)
    reprovados = []
    investigacao_atual = None

    for desafio in desafios_curados():
        if desafio["investigacao"] != investigacao_atual:
            investigacao_atual = desafio["investigacao"]
            print(f"\n== {investigacao_atual} ==")
        ok, detalhe = resolver(consulta, desafio["chave"], desafio["flag"])
        marca = "PASS" if ok else "FALHA"
        if not ok:
            reprovados.append(desafio["nome"])
        print(f"  {marca}: {desafio['nome'][:34]:<36} {detalhe[:74]}")

    print()
    total = len(desafios_curados())
    print(f"{total - len(reprovados)} de {total} desafios resolvem contra os dados")
    if reprovados:
        print("reprovados: " + ", ".join(reprovados))
        raise SystemExit(1)


if __name__ == "__main__":
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--indice", default="leonardo")
    analisador.add_argument("--container", default="local-elasticsearch-1")
    argumentos = analisador.parse_args()
    executar(argumentos.container, argumentos.indice)
