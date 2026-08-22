"""Elasticsearch summary for the Hikari SIEM entrypoint."""

from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel


class TermBucket(BaseModel):
    key: str
    count: int


class RecentEvent(BaseModel):
    timestamp: Optional[str]
    source_ip: Optional[str]
    destination_ip: Optional[str]
    destination_port: Optional[str]
    service: Optional[str]
    severity: Optional[str]
    message: Optional[str]
    url: Optional[str]


class SiemSummary(BaseModel):
    index_name: str
    total_events: int
    network_events: int
    classified_events: int
    severity: List[TermBucket]
    datasets: List[TermBucket]
    countries: List[TermBucket]
    processes: List[TermBucket]
    event_names: List[TermBucket]
    source_ips: List[TermBucket]
    destination_ips: List[TermBucket]
    destination_ports: List[TermBucket]
    recent: List[RecentEvent]

from CTFd.plugins.hikari_plugin.settings import settings

def build_siem_summary(index_name: str = "competition1") -> SiemSummary:
    summary_response = requests.post(
        f"{elastic_url()}/{index_name}/_search",
        json=summary_query(),
        timeout=10,
    )
    if summary_response.status_code == 404:
        return empty_summary(index_name)
    summary_response.raise_for_status()
    summary_payload = summary_response.json()

    recent_response = requests.post(
        f"{elastic_url()}/{index_name}/_search",
        json=recent_events_query(),
        timeout=10,
    )
    recent_response.raise_for_status()
    recent_payload = recent_response.json()

    return SiemSummary(
        index_name=index_name,
        total_events=total_hits(summary_payload),
        network_events=filter_count(summary_payload, "network_events"),
        classified_events=filter_count(summary_payload, "classified_events"),
        severity=term_buckets(summary_payload, "severity"),
        datasets=term_buckets(summary_payload, "datasets"),
        countries=term_buckets(summary_payload, "countries"),
        processes=term_buckets(summary_payload, "processes"),
        event_names=term_buckets(summary_payload, "event_names"),
        source_ips=term_buckets(summary_payload, "source_ips"),
        destination_ips=term_buckets(summary_payload, "destination_ips"),
        destination_ports=term_buckets(summary_payload, "destination_ports"),
        recent=recent_events(recent_payload),
    )


def empty_summary(index_name: str) -> SiemSummary:
    return SiemSummary(
        index_name=index_name,
        total_events=0,
        network_events=0,
        classified_events=0,
        severity=[],
        datasets=[],
        countries=[],
        processes=[],
        event_names=[],
        source_ips=[],
        destination_ips=[],
        destination_ports=[],
        recent=[],
    )


def elastic_url() -> str:
    return settings().elastic_url.rstrip("/")


# O painel foi escrito contra um esquema anterior, com nomes de coluna no
# estilo do appliance de origem ("Source IP", "Fortinet Message (custom)").
# O índice passou a usar nomes ECS e ninguém reescreveu as agregações, então
# todas passaram a devolver zero enquanto o total de eventos, que não depende
# de campo nenhum, continuava certo. Daí a tela mostrar quase meio milhão de
# eventos e nenhum sinal.
CAMPOS = {
    "severity": "event.severity_label.keyword",
    "datasets": "event.dataset.keyword",
    "countries": "source.geo.country_iso_code.keyword",
    "processes": "process.name.keyword",
    "event_names": "event.action.keyword",
    "source_ips": "source.ip",
    "destination_ips": "destination.ip",
    "destination_ports": "destination.port",
}


def summary_query() -> Dict[str, Any]:
    agregacoes: Dict[str, Any] = {
        "network_events": {"filter": {"exists": {"field": "source.ip"}}},
        "classified_events": {"filter": {"exists": {"field": "event.severity_label.keyword"}}},
    }
    for nome, campo in CAMPOS.items():
        agregacoes[nome] = {"terms": {"field": campo, "size": 6}}
    return {"size": 0, "track_total_hits": True, "aggs": agregacoes}


def recent_events_query() -> Dict[str, Any]:
    return {
        "size": 12,
        "track_total_hits": False,
        "query": {"exists": {"field": "event.action.keyword"}},
        "sort": [{"@timestamp": {"order": "desc", "unmapped_type": "date"}}],
        "_source": [
            "@timestamp",
            "source.ip",
            "destination.ip",
            "destination.port",
            "event.dataset",
            "event.action",
            "event.severity_label",
            "message",
            "url.full",
        ],
    }


def total_hits(payload: Dict[str, Any]) -> int:
    total = payload.get("hits", {}).get("total", 0)
    if isinstance(total, dict):
        return int(total.get("value", 0))
    return int(total)


def filter_count(payload: Dict[str, Any], aggregation_name: str) -> int:
    return int(payload.get("aggregations", {}).get(aggregation_name, {}).get("doc_count", 0))


def term_buckets(payload: Dict[str, Any], aggregation_name: str) -> List[TermBucket]:
    buckets = payload.get("aggregations", {}).get(aggregation_name, {}).get("buckets", [])
    return [
        TermBucket(key=display_key(bucket.get("key", "-")), count=int(bucket.get("doc_count", 0)))
        for bucket in buckets
    ]


def recent_events(payload: Dict[str, Any]) -> List[RecentEvent]:
    hits = payload.get("hits", {}).get("hits", [])
    return [recent_event(hit.get("_source", {})) for hit in hits]


def aninhado(documento: Dict[str, Any], caminho: str) -> Any:
    """Lê um campo pontuado do _source, nas duas formas que o índice recebe.

    O índice guarda o ponto como parte do nome do campo, e as fontes discordam
    de como escrevem o documento: as coleções geradas mandam `source` aninhado,
    as do QRadar mandam a chave `"source.ip"` inteira. Quem lê só a forma
    aninhada devolve vazio para metade do índice, e a tabela de eventos
    recentes aparece em branco sem que nada acuse erro.
    """
    if caminho in documento:
        return documento[caminho]
    atual: Any = documento
    for parte in caminho.split("."):
        if not isinstance(atual, dict):
            return None
        atual = atual.get(parte)
    return atual


def recent_event(source: Dict[str, Any]) -> RecentEvent:
    return RecentEvent(
        timestamp=source.get("@timestamp"),
        source_ip=aninhado(source, "source.ip"),
        destination_ip=aninhado(source, "destination.ip"),
        destination_port=string_or_none(aninhado(source, "destination.port")),
        service=aninhado(source, "event.dataset"),
        severity=aninhado(source, "event.severity_label"),
        message=source.get("message") or aninhado(source, "event.action"),
        url=aninhado(source, "url.full"),
    )


def string_or_none(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def display_key(value: Any) -> str:
    key = str(value).strip()
    if len(key) >= 2 and key[0] == '"' and key[-1] == '"':
        return key[1:-1]
    return key or "-"
