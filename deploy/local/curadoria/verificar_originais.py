"""Resolve cada desafio original pelo gabarito e compara com a flag cadastrada.

Executa a consulta que a dica do próprio desafio manda fazer e confere se ela
produz a resposta registrada. Um desafio que não fecha aqui é um desafio que o
competidor não consegue resolver seguindo a orientação que a plataforma dá.
"""

import argparse
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, str(Path(__file__).parent))

from conferencias_originais import CONFERENCIAS_ORIGINAIS

ENVELOPE = re.compile(r"^\s*flag\{(.*)\}\s*$", re.IGNORECASE | re.DOTALL)


class Indice:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    def buscar(self, corpo: Dict[str, Any]) -> Dict[str, Any]:
        corpo.setdefault("track_total_hits", True)
        return requests.post(f"{self.url}/_search", json=corpo, timeout=120).json()


def total(resposta: Dict[str, Any]) -> int:
    valor = resposta.get("hits", {}).get("total", 0)
    return valor.get("value", 0) if isinstance(valor, dict) else int(valor)


def filtros_de(conferencia: Dict[str, Any]) -> List[Dict[str, Any]]:
    saida: List[Dict[str, Any]] = []
    if "conjunto" in conferencia:
        saida.append({"term": {"event.dataset.keyword": conferencia["conjunto"]}})
    for campo, valor in (conferencia.get("filtro") or {}).items():
        saida.append({"term": {campo: valor}})
    for campo, limites in (conferencia.get("faixa") or {}).items():
        saida.append({"range": {campo: limites}})
    return saida


def baldes(indice: Indice, conferencia: Dict[str, Any], tamanho: int = 30):
    agregacao: Dict[str, Any] = {"terms": {"field": conferencia["campo"], "size": tamanho}}
    if conferencia.get("soma"):
        agregacao = {
            "terms": {"field": conferencia["campo"], "size": tamanho,
                      "order": {"volume": "desc"}},
            "aggs": {"volume": {"sum": {"field": conferencia["soma"]}}},
        }
    resposta = indice.buscar({
        "size": 0, "query": {"bool": {"filter": filtros_de(conferencia)}},
        "aggs": {"v": agregacao}})
    return [(str(b["key"]), b["doc_count"]) for b in
            resposta.get("aggregations", {}).get("v", {}).get("buckets", [])]


def resolver(indice: Indice, conferencia: Dict[str, Any]) -> Optional[str]:
    modo = conferencia["modo"]
    consulta = {"bool": {"filter": filtros_de(conferencia)}}

    if modo == "contagem":
        return str(total(indice.buscar({"size": 0, "query": consulta})))

    if modo == "cardinalidade":
        r = indice.buscar({"size": 0, "query": consulta, "aggs": {
            "d": {"cardinality": {"field": conferencia["campo"], "precision_threshold": 40000}}}})
        return str(r["aggregations"]["d"]["value"])

    if modo == "maximo":
        r = indice.buscar({"size": 0, "query": consulta,
                           "aggs": {"m": {"max": {"field": conferencia["campo"]}}}})
        valor = r["aggregations"]["m"]["value"]
        return str(int(valor)) if valor is not None else None

    if modo == "primeiro_carimbo":
        # O competidor lê o horário no Kibana, que o exibe no fuso do navegador.
        # A flag guarda essa forma, com deslocamento de Brasília, e não o UTC
        # cru que o índice armazena.
        r = indice.buscar({"size": 1, "query": consulta, "sort": [{"@timestamp": "asc"}],
                           "_source": ["@timestamp"]})
        acertos = r["hits"]["hits"]
        if not acertos:
            return None
        bruto = acertos[0]["_source"]["@timestamp"]
        momento = datetime.strptime(bruto, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        local = momento.astimezone(ZoneInfo("America/Sao_Paulo"))
        # O Kibana mostra milissegundos, não microssegundos; a flag guarda a
        # forma exibida, então a comparação tem de usar a mesma precisão.
        return local.isoformat(timespec="milliseconds")

    if modo == "primeiro":
        r = indice.buscar({"size": 1, "query": consulta, "sort": [{"@timestamp": "asc"}],
                           "_source": [conferencia["campo"].replace(".keyword", "")]})
        acertos = r["hits"]["hits"]
        if not acertos:
            return None
        atual: Any = acertos[0]["_source"]
        for parte in conferencia["campo"].replace(".keyword", "").split("."):
            atual = atual.get(parte) if isinstance(atual, dict) else None
        return str(atual) if atual is not None else None

    encontrados = baldes(indice, conferencia)
    if not encontrados:
        return None
    if modo in ("topo", "topo_por_soma"):
        return encontrados[0][0]
    if modo in ("segundo", "segundo_por_soma"):
        return encontrados[1][0] if len(encontrados) > 1 else None
    if modo == "terceiro":
        return encontrados[2][0] if len(encontrados) > 2 else None
    if modo == "entre_os_valores":
        # Alguns desafios identificam a resposta por uma propriedade do nome,
        # não pela frequência. Basta que ela esteja entre os valores do recorte.
        return None
    if modo == "raro":
        return min(encontrados, key=lambda par: par[1])[0]
    if modo == "contagem_do_topo":
        return str(encontrados[0][1])
    return None


def executar(url_indice: str) -> None:
    from CTFd import create_app

    indice = Indice(url_indice)
    app = create_app()
    with app.app_context():
        from CTFd.models import Challenges, Flags

        resolvidos, falhas, sem_gabarito = 0, [], []
        for nome, conferencia in CONFERENCIAS_ORIGINAIS.items():
            desafio = Challenges.query.filter_by(name=nome).first()
            if desafio is None:
                sem_gabarito.append(nome)
                continue
            bandeira = Flags.query.filter_by(challenge_id=desafio.id, type="static").first()
            achado = ENVELOPE.match(bandeira.content or "")
            esperado = (achado.group(1) if achado else (bandeira.content or "")).strip()

            if conferencia["modo"] == "entre_os_valores":
                valores = [v.lower() for v, _ in baldes(indice, conferencia)]
                igual = esperado.lower() in valores
                obtido = esperado if igual else (valores[0] if valores else None)
            else:
                obtido = resolver(indice, conferencia)
                igual = obtido is not None and obtido.lower() == esperado.lower()
            if igual:
                resolvidos += 1
            else:
                falhas.append((nome, esperado, obtido))
            print(f"  {'RESOLVE' if igual else 'FALHA  '} {nome[:34]:<36} "
                  f"esperado {esperado[:26]:<28} obtido {str(obtido)[:26]}")

        print()
        print(f"{resolvidos} de {len(CONFERENCIAS_ORIGINAIS)} desafios originais resolvem pelo gabarito")
        if sem_gabarito:
            print("sem desafio correspondente: " + ", ".join(sem_gabarito))
        if falhas:
            raise SystemExit(1)


if __name__ == "__main__":
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--indice", default="http://elasticsearch:9200/competition1")
    executar(analisador.parse_args().indice)
