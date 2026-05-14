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
    network_events: int
    classified_events: int
    severity: List[TermBucket]
    services: List[TermBucket]
    countries: List[TermBucket]
    messages: List[TermBucket]
    event_names: List[TermBucket]
    source_ips: List[TermBucket]
    destination_ips: List[TermBucket]
    destination_ports: List[TermBucket]
    recent: List[RecentEvent]


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
        services=term_buckets(summary_payload, "services"),
        countries=term_buckets(summary_payload, "countries"),
        messages=term_buckets(summary_payload, "messages"),
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
        services=[],
        countries=[],
        messages=[],
        event_names=[],
        source_ips=[],
        destination_ips=[],
        destination_ports=[],
        recent=[],
    )


def elastic_url() -> str:
    return os.environ.get("ELASTIC_URL", "http://elasticsearch:9200").rstrip("/")


def summary_query() -> Dict[str, Any]:
    return {
        "size": 0,
        "track_total_hits": True,
        "aggs": {
            "network_events": {"filter": {"exists": {"field": "Source IP.keyword"}}},
            "classified_events": {
                "filter": {"exists": {"field": "Threat Severity (custom).keyword"}}
            },
            "severity": {
                "terms": {
                    "field": "Threat Severity (custom).keyword",
                    "size": 6,
                }
            },
            "services": {
                "terms": {
                    "field": "Fortinet Service (custom).keyword",
                    "size": 6,
                }
            },
            "countries": {
                "terms": {
                    "field": "Destination Country (custom).keyword",
                    "size": 6,
                }
            },
            "messages": {
                "terms": {
                    "field": "Fortinet Message (custom).keyword",
                    "size": 6,
                }
            },
            "event_names": {"terms": {"field": "Event Name.keyword", "size": 6}},
            "source_ips": {"terms": {"field": "Source IP.keyword", "size": 6}},
            "destination_ips": {"terms": {"field": "Destination IP.keyword", "size": 6}},
            "destination_ports": {"terms": {"field": "Destination Port.keyword", "size": 6}},
        },
    }


def recent_events_query() -> Dict[str, Any]:
    return {
        "size": 12,
        "track_total_hits": False,
        "query": {
            "bool": {
                "should": [
                    {"exists": {"field": "Source IP.keyword"}},
                    {"exists": {"field": "Event Name.keyword"}},
                    {"exists": {"field": "Fortinet Message (custom).keyword"}},
                ],
                "minimum_should_match": 1,
            }
        },
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


def display_key(value: Any) -> str:
    key = str(value).strip()
    if len(key) >= 2 and key[0] == '"' and key[-1] == '"':
        return key[1:-1]
    return key or "-"
