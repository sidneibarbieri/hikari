"""Elasticsearch summary for the Hikari SIEM entrypoint."""

import os
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
    severity: List[TermBucket]
    source_ips: List[TermBucket]
    destination_ips: List[TermBucket]
    destination_ports: List[TermBucket]
    recent: List[RecentEvent]


def build_siem_summary(index_name: str = "competition1") -> SiemSummary:
    response = requests.post(
        f"{elastic_url()}/{index_name}/_search",
        json=summary_query(),
        timeout=10,
    )
    if response.status_code == 404:
        return empty_summary(index_name)
    response.raise_for_status()
    payload = response.json()
    return SiemSummary(
        index_name=index_name,
        total_events=total_hits(payload),
        severity=term_buckets(payload, "severity"),
        source_ips=term_buckets(payload, "source_ips"),
        destination_ips=term_buckets(payload, "destination_ips"),
        destination_ports=term_buckets(payload, "destination_ports"),
        recent=recent_events(payload),
    )


def empty_summary(index_name: str) -> SiemSummary:
    return SiemSummary(
        index_name=index_name,
        total_events=0,
        severity=[],
        source_ips=[],
        destination_ips=[],
        destination_ports=[],
        recent=[],
    )


def elastic_url() -> str:
    return os.environ.get("ELASTIC_URL", "http://elasticsearch:9200").rstrip("/")


def summary_query() -> Dict[str, Any]:
    return {
        "size": 12,
        "sort": [{"@timestamp": {"order": "desc", "unmapped_type": "date"}}],
        "_source": [
            "@timestamp",
            "Source IP",
            "Destination IP",
            "Destination Port",
            "Fortinet Service (custom)",
            "Fortinet Message (custom)",
            "Threat Severity (custom)",
            "URL (custom)",
            "Event Name",
        ],
        "aggs": {
            "severity": {
                "terms": {
                    "field": "Threat Severity (custom).keyword",
                    "size": 6,
                    "missing": "unknown",
                }
            },
            "source_ips": {"terms": {"field": "Source IP.keyword", "size": 6}},
            "destination_ips": {"terms": {"field": "Destination IP.keyword", "size": 6}},
            "destination_ports": {"terms": {"field": "Destination Port.keyword", "size": 6}},
        },
    }


def total_hits(payload: Dict[str, Any]) -> int:
    total = payload.get("hits", {}).get("total", 0)
    if isinstance(total, dict):
        return int(total.get("value", 0))
    return int(total)


def term_buckets(payload: Dict[str, Any], aggregation_name: str) -> List[TermBucket]:
    buckets = payload.get("aggregations", {}).get(aggregation_name, {}).get("buckets", [])
    return [
        TermBucket(key=str(bucket.get("key", "-")), count=int(bucket.get("doc_count", 0)))
        for bucket in buckets
    ]


def recent_events(payload: Dict[str, Any]) -> List[RecentEvent]:
    hits = payload.get("hits", {}).get("hits", [])
    return [recent_event(hit.get("_source", {})) for hit in hits]


def recent_event(source: Dict[str, Any]) -> RecentEvent:
    return RecentEvent(
        timestamp=source.get("@timestamp"),
        source_ip=source.get("Source IP"),
        destination_ip=source.get("Destination IP"),
        destination_port=string_or_none(source.get("Destination Port")),
        service=source.get("Fortinet Service (custom)"),
        severity=source.get("Threat Severity (custom)"),
        message=source.get("Fortinet Message (custom)") or source.get("Event Name"),
        url=source.get("URL (custom)"),
    )


def string_or_none(value: Any) -> Optional[str]:
    return None if value is None else str(value)
