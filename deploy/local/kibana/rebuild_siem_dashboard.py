"""Rebuild the Hikari SIEM dashboard in Kibana 8.19 via REST API.

This script creates saved objects directly via POST (not _import), which
avoids Kibana's NDJSON import normalization of panelRefName/reference names.

Visualization types used (all confirmed working in Kibana 8.19.15):
  histogram  — bar charts and date-histogram time series
  pie        — severity distribution, countries
  heatmap    — port × source IP matrix
  table      — severity counts, top URLs, top messages, src→dst→port
  search     — recent network events (Discover saved search)

Types intentionally avoided (do not render correctly in 8.19.15):
  metric  — legacy Visualize renderer removed
  line    — legacy renderer removed
  area    — legacy renderer removed
  tsvb    — broken reference resolution in import pipeline
  timelion — broken reference resolution in import pipeline

Usage (from repo root):
    python deploy/local/kibana/rebuild_siem_dashboard.py
"""

import json
import os
import sys
import time
from pathlib import Path

import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Allow callers to override the base URL via environment variable so the same
# script works both locally (localhost:5601) and when executed inside a Docker
# container where Kibana is reached by service name (kibana:5601).
KIBANA_BASE = os.environ.get(
    "KIBANA_BASE", "http://localhost:5601/hikari/kibana"
)
INDEX_ID = "competition1"
VERSION = "8.19.0"
NDJSON_PATH = Path("deploy/local/kibana/hikari-siem.ndjson")


def _post(path: str, body: dict) -> dict:
    """POST a saved object to the Kibana API inside the container."""
    url = f"{KIBANA_BASE}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("kbn-xsrf", "true")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        return {"error": str(exc), "body": body_text}


def _create_saved_object(
    obj_type: str,
    obj_id: str,
    attributes: dict,
    references: list | None = None,
    overwrite: bool = True,
) -> dict:
    """Create or update a Kibana saved object via POST."""
    qs = "?overwrite=true" if overwrite else ""
    path = f"/api/saved_objects/{obj_type}/{obj_id}{qs}"
    body: dict = {"attributes": attributes}
    if references is not None:
        body["references"] = references
    return _post(path, body)


# ---------------------------------------------------------------------------
# Index pattern
# ---------------------------------------------------------------------------


def create_index_pattern() -> None:
    result = _create_saved_object(
        "index-pattern",
        INDEX_ID,
        {
            "title": INDEX_ID,
            "timeFieldName": "@timestamp",
        },
        references=[],
    )
    ok = "id" in result
    print(f"  index-pattern competition1: {'✓' if ok else '✗ ' + str(result)}")


# ---------------------------------------------------------------------------
# Visualization helpers
# ---------------------------------------------------------------------------

_IDX_REF = {"type": "index-pattern", "name": "kibanaSavedObjectMeta.searchSourceJSON.index", "id": INDEX_ID}


def _searchsource(query: str = "") -> str:
    return json.dumps({
        "query": {"language": "kuery", "query": query},
        "filter": [],
        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
    })


def _vis_attrs(title: str, vis_type: str, params: dict, aggs: list, query: str = "") -> dict:
    visstate = {"title": title, "type": vis_type, "params": params, "aggs": aggs}
    return {
        "title": title,
        "visState": json.dumps(visstate),
        "uiStateJSON": "{}",
        "version": 1,
        "kibanaSavedObjectMeta": {"searchSourceJSON": _searchsource(query)},
    }


def _create_viz(vid: str, title: str, vis_type: str, params: dict, aggs: list, query: str = "") -> None:
    result = _create_saved_object(
        "visualization", vid,
        _vis_attrs(title, vis_type, params, aggs, query),
        references=[_IDX_REF],
    )
    ok = "id" in result
    print(f"  viz/{vid[:35]}: {'✓' if ok else '✗ ' + str(result)[:100]}")


# ---------------------------------------------------------------------------
# Row 1: Severity count table (replaces broken TSVB/metric tiles)
# ---------------------------------------------------------------------------


def create_severity_count_table() -> None:
    params = {
        "perPage": 10,
        "showPartialRows": False,
        "showMetricsAtAllLevels": False,
        "sort": {"columnIndex": 1, "direction": "desc"},
        "showTotal": True,
        "totalFunc": "sum",
        "percentageCol": "",
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {
                "field": "Threat Severity (custom).keyword",
                "size": 10,
                "order": "desc",
                "orderBy": "1",
                "otherBucket": False,
            },
        },
    ]
    _create_viz("siem-severity-table", "Contagem por Severidade", "table", params, aggs)


# ---------------------------------------------------------------------------
# Row 1b: Events over time — date histogram (replaces broken timelion/line)
# ---------------------------------------------------------------------------


def create_events_over_time() -> None:
    params = {
        "type": "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{
            "id": "CategoryAxis-1", "type": "category", "position": "bottom", "show": True,
            "style": {}, "scale": {"type": "linear"}, "labels": {"show": True, "truncate": 100},
            "title": {},
        }],
        "valueAxes": [{
            "id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value", "position": "left",
            "show": True, "style": {}, "scale": {"type": "linear", "mode": "normal"},
            "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
            "title": {"text": "Contagem de eventos"},
        }],
        "seriesParams": [{
            "show": True, "type": "histogram", "mode": "stacked",
            "data": {"label": "Contagem", "id": "1"},
            "valueAxis": "ValueAxis-1",
            "drawLinesBetweenPoints": True,
            "showCircles": True,
        }],
        "addTooltip": True,
        "addLegend": True,
        "legendPosition": "right",
        "times": [],
        "addTimeMarker": False,
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "date_histogram", "schema": "segment",
            "params": {
                "field": "@timestamp",
                "useNormalizedEsInterval": True,
                "interval": "auto",
                "time_zone": "UTC",
                "drop_partials": False,
                "customInterval": "2h",
                "min_doc_count": 1,
                "extended_bounds": {},
            },
        },
    ]
    _create_viz("siem-events-over-time", "Eventos ao longo do tempo", "histogram", params, aggs)


# ---------------------------------------------------------------------------
# Row 1c: Severity over time (stacked) — also date histogram
# ---------------------------------------------------------------------------


def create_severity_over_time() -> None:
    params = {
        "type": "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{
            "id": "CategoryAxis-1", "type": "category", "position": "bottom", "show": True,
            "style": {}, "scale": {"type": "linear"}, "labels": {"show": True, "truncate": 100},
            "title": {},
        }],
        "valueAxes": [{
            "id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value", "position": "left",
            "show": True, "style": {}, "scale": {"type": "linear", "mode": "normal"},
            "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
            "title": {"text": "Eventos"},
        }],
        "seriesParams": [{
            "show": True, "type": "histogram", "mode": "stacked",
            "data": {"label": "Contagem", "id": "1"},
            "valueAxis": "ValueAxis-1",
            "drawLinesBetweenPoints": True,
            "showCircles": True,
        }],
        "addTooltip": True,
        "addLegend": True,
        "legendPosition": "right",
        "times": [],
        "addTimeMarker": False,
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "date_histogram", "schema": "segment",
            "params": {
                "field": "@timestamp",
                "interval": "auto",
                "time_zone": "UTC",
                "drop_partials": False,
                "customInterval": "2h",
                "min_doc_count": 1,
                "extended_bounds": {},
            },
        },
        {
            "id": "3", "enabled": True, "type": "terms", "schema": "group",
            "params": {
                "field": "Threat Severity (custom).keyword",
                "size": 5,
                "order": "desc",
                "orderBy": "1",
            },
        },
    ]
    _create_viz("siem-severity-over-time", "Severidade ao longo do tempo", "histogram", params, aggs)


# ---------------------------------------------------------------------------
# Severity distribution pie
# ---------------------------------------------------------------------------


def create_severity_pie() -> None:
    params = {
        "type": "pie",
        "addTooltip": True,
        "addLegend": True,
        "legendPosition": "right",
        "isDonut": True,
        "labels": {
            "show": False, "values": True, "last_level": True,
            "truncate": 100, "position": "default",
        },
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "segment",
            "params": {
                "field": "Threat Severity (custom).keyword",
                "size": 10,
                "order": "desc",
                "orderBy": "1",
                "otherBucket": False,
            },
        },
    ]
    _create_viz("siem-severity-pie", "Distribuição de Severidade", "pie", params, aggs)


# ---------------------------------------------------------------------------
# Top source IPs bar
# ---------------------------------------------------------------------------


def create_top_src_ips() -> None:
    params = {
        "type": "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{
            "id": "CategoryAxis-1", "type": "category", "position": "left", "show": True,
            "style": {}, "scale": {"type": "linear"}, "labels": {"show": True, "rotate": 0, "truncate": 200},
            "title": {},
        }],
        "valueAxes": [{
            "id": "ValueAxis-1", "name": "BottomAxis-1", "type": "value", "position": "bottom",
            "show": True, "style": {}, "scale": {"type": "linear", "mode": "normal"},
            "labels": {"show": True, "rotate": 0, "filter": True, "truncate": 100},
            "title": {"text": "Contagem"},
        }],
        "seriesParams": [{
            "show": True, "type": "histogram", "mode": "normal",
            "data": {"label": "Contagem", "id": "1"},
            "valueAxis": "ValueAxis-1",
            "drawLinesBetweenPoints": True, "showCircles": True,
        }],
        "addTooltip": True,
        "addLegend": False,
        "legendPosition": "right",
        "times": [],
        "addTimeMarker": False,
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {"field": "Source IP.keyword", "size": 10, "order": "desc", "orderBy": "1", "otherBucket": False},
        },
    ]
    _create_viz("siem-top-src-ips", "Top IPs de Origem", "histogram", params, aggs)


def create_top_dst_ips() -> None:
    params = {
        "type": "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{
            "id": "CategoryAxis-1", "type": "category", "position": "left", "show": True,
            "style": {}, "scale": {"type": "linear"}, "labels": {"show": True, "rotate": 0, "truncate": 200},
            "title": {},
        }],
        "valueAxes": [{
            "id": "ValueAxis-1", "name": "BottomAxis-1", "type": "value", "position": "bottom",
            "show": True, "style": {}, "scale": {"type": "linear", "mode": "normal"},
            "labels": {"show": True, "rotate": 0, "filter": True, "truncate": 100},
            "title": {"text": "Contagem"},
        }],
        "seriesParams": [{
            "show": True, "type": "histogram", "mode": "normal",
            "data": {"label": "Contagem", "id": "1"},
            "valueAxis": "ValueAxis-1",
        }],
        "addTooltip": True, "addLegend": False,
        "legendPosition": "right", "times": [], "addTimeMarker": False,
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {"field": "Destination IP.keyword", "size": 10, "order": "desc", "orderBy": "1", "otherBucket": False},
        },
    ]
    _create_viz("siem-top-dst-ips", "Top IPs de Destino", "histogram", params, aggs)


def create_top_dst_ports() -> None:
    params = {
        "type": "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{
            "id": "CategoryAxis-1", "type": "category", "position": "left", "show": True,
            "style": {}, "scale": {"type": "linear"}, "labels": {"show": True, "rotate": 0, "truncate": 200},
            "title": {},
        }],
        "valueAxes": [{
            "id": "ValueAxis-1", "name": "BottomAxis-1", "type": "value", "position": "bottom",
            "show": True, "style": {}, "scale": {"type": "linear", "mode": "normal"},
            "labels": {"show": True, "rotate": 0, "filter": True, "truncate": 100},
            "title": {"text": "Contagem"},
        }],
        "seriesParams": [{"show": True, "type": "histogram", "mode": "normal", "data": {"label": "Contagem", "id": "1"}, "valueAxis": "ValueAxis-1"}],
        "addTooltip": True, "addLegend": False,
        "legendPosition": "right", "times": [], "addTimeMarker": False,
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {"field": "Destination Port.keyword", "size": 15, "order": "desc", "orderBy": "1", "otherBucket": False},
        },
    ]
    _create_viz("siem-top-dst-ports", "Top Portas de Destino", "histogram", params, aggs)


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------


def create_heatmap() -> None:
    params = {
        "addTooltip": True,
        "addLegend": True,
        "enableHover": False,
        "legendPosition": "right",
        "times": [],
        "colorsNumber": 4,
        "colorSchema": "Reds",
        "setColorRange": False,
        "colorsRange": [],
        "invertColors": False,
        "percentageMode": False,
        "valueAxes": [{
            "show": False,
            "id": "ValueAxis-1",
            "type": "value",
            "scale": {"type": "linear", "defaultYExtents": False},
            "labels": {"show": False, "rotate": 0, "color": "black"},
        }],
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "segment",
            "params": {"field": "Source IP.keyword", "size": 10, "order": "desc", "orderBy": "1"},
        },
        {
            "id": "3", "enabled": True, "type": "terms", "schema": "group",
            "params": {"field": "Destination Port.keyword", "size": 10, "order": "desc", "orderBy": "1"},
        },
    ]
    _create_viz("siem-heatmap", "Heatmap Porta × Origem", "heatmap", params, aggs)


# ---------------------------------------------------------------------------
# Countries donut
# ---------------------------------------------------------------------------


def create_countries_donut() -> None:
    params = {
        "type": "pie",
        "addTooltip": True,
        "addLegend": True,
        "legendPosition": "right",
        "isDonut": True,
        "labels": {"show": False, "values": True, "last_level": True, "truncate": 100, "position": "default"},
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "segment",
            "params": {"field": "Destination Country (custom).keyword", "size": 10, "order": "desc", "orderBy": "1", "otherBucket": False},
        },
    ]
    _create_viz("siem-countries-donut", "Top Países de Destino", "pie", params, aggs)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def _table_params() -> dict:
    return {
        "perPage": 10,
        "showPartialRows": False,
        "showMetricsAtAllLevels": False,
        "sort": {"columnIndex": None, "direction": None},
        "showTotal": False,
        "totalFunc": "sum",
        "percentageCol": "",
    }


def create_fortinet_messages() -> None:
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {"id": "2", "enabled": True, "type": "terms", "schema": "bucket",
         "params": {"field": "Event Name.keyword", "size": 15, "order": "desc", "orderBy": "1", "otherBucket": False}},
    ]
    _create_viz("siem-fortinet-messages", "Top Eventos por Tipo", "table", _table_params(), aggs)


def create_top_urls() -> None:
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {"id": "2", "enabled": True, "type": "terms", "schema": "bucket",
         "params": {"field": "Service Name (custom).keyword", "size": 15, "order": "desc", "orderBy": "1", "otherBucket": False}},
    ]
    _create_viz("siem-top-urls", "Top Serviços de Rede", "table", _table_params(), aggs)


def create_src_dst_port_table() -> None:
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {"id": "2", "enabled": True, "type": "terms", "schema": "bucket",
         "params": {"field": "Source IP.keyword", "size": 5, "order": "desc", "orderBy": "1", "otherBucket": False}},
        {"id": "3", "enabled": True, "type": "terms", "schema": "bucket",
         "params": {"field": "Destination IP.keyword", "size": 5, "order": "desc", "orderBy": "1", "otherBucket": False}},
        {"id": "4", "enabled": True, "type": "terms", "schema": "bucket",
         "params": {"field": "Destination Port.keyword", "size": 5, "order": "desc", "orderBy": "1", "otherBucket": False}},
    ]
    _create_viz("siem-src-dst-port", "Top Origem → Destino → Porta", "table", _table_params(), aggs)


# ---------------------------------------------------------------------------
# Discover saved search
# ---------------------------------------------------------------------------


def create_recent_connections() -> None:
    columns = [
        "@timestamp", "Source IP", "Destination IP", "Destination Port",
        "network.transport", "Threat Severity (custom)", "Fortinet Message (custom)",
    ]
    searchsource = json.dumps({
        "query": {"language": "kuery", "query": ""},
        "filter": [],
        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
        "highlight": {
            "pre_tags": ["@kibana-highlighted-field@"],
            "post_tags": ["@/kibana-highlighted-field@"],
            "fields": {"*": {}},
            "fragment_size": 2147483647,
        },
    })
    attrs = {
        "title": "Conexões de Rede Recentes",
        "description": "Eventos de rede mais recentes para investigação.",
        "columns": columns,
        "sort": [["@timestamp", "desc"]],
        "kibanaSavedObjectMeta": {"searchSourceJSON": searchsource},
    }
    result = _create_saved_object(
        "search", "siem-recent-connections",
        attrs,
        references=[_IDX_REF],
    )
    ok = "id" in result
    print(f"  search/siem-recent-connections: {'✓' if ok else '✗ ' + str(result)[:100]}")


# ---------------------------------------------------------------------------
# State-of-the-art SOC panels (v2)
#
# Added 2026-05 to bring the dashboard closer to Splunk Enterprise Security
# and Elastic SIEM defaults: severity KPIs at the top for at-a-glance triage,
# detection-name and IOC tables for hunt pivot, suspicious process tree for
# host-level investigation, and a lateral-movement signal (unique-destination
# cardinality) that traditional volume-based panels miss.
# ---------------------------------------------------------------------------


def _severity_metric(severity: str) -> dict:
    """Build a Kibana 'metric' visualization filtered to one severity level.

    SOC dashboards lead with severity counts so the analyst sees triage scope
    in the first glance. Each tile uses the metric vis (single big number)
    filtered by a KQL query on Threat Severity.
    """
    label_map = {"critical": "Críticos", "high": "Altos", "medium": "Médios", "low": "Baixos"}
    color_map = {"critical": "#ef4444", "high": "#f97316", "medium": "#f59e0b", "low": "#10b981"}
    params = {
        "addTooltip": True,
        "addLegend": False,
        "type": "metric",
        "metric": {
            "percentageMode": False,
            "useRanges": False,
            "colorSchema": "Green to Red",
            "metricColorMode": "None",
            "colorsRange": [{"from": 0, "to": 10000}],
            "labels": {"show": True},
            "invertColors": False,
            "style": {
                "bgFill": "transparent",
                "bgColor": False,
                "labelColor": False,
                "subText": "",
                "fontSize": 48,
            },
        },
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric",
         "params": {"customLabel": label_map.get(severity, severity)}},
    ]
    query = f'"Threat Severity (custom).keyword": "{severity}"'
    _ = color_map  # palette referenced for future custom color application
    return {"params": params, "aggs": aggs, "query": query}


def create_severity_metrics() -> None:
    """Four severity KPI tiles (Critical, High, Medium, Low)."""
    for severity in ("critical", "high", "medium", "low"):
        spec = _severity_metric(severity)
        _create_viz(
            f"siem-kpi-{severity}",
            f"Severidade — {severity.title()}",
            "metric",
            spec["params"],
            spec["aggs"],
            spec["query"],
        )


def create_top_detect_names() -> None:
    """Top detection names — what controls are actually firing right now."""
    params = {
        "type": "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{
            "id": "CategoryAxis-1", "type": "category", "position": "left", "show": True,
            "style": {}, "scale": {"type": "linear"}, "labels": {"show": True, "truncate": 100, "rotate": 0},
            "title": {},
        }],
        "valueAxes": [{
            "id": "ValueAxis-1", "name": "BottomAxis-1", "type": "value", "position": "bottom",
            "show": True, "style": {}, "scale": {"type": "linear", "mode": "normal"},
            "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
            "title": {"text": "Eventos"},
        }],
        "seriesParams": [{
            "show": True, "type": "histogram", "mode": "normal",
            "data": {"label": "Contagem", "id": "1"},
            "valueAxis": "ValueAxis-1",
            "drawLinesBetweenPoints": True,
            "showCircles": True,
        }],
        "addTooltip": True, "addLegend": False, "legendPosition": "right",
        "times": [], "addTimeMarker": False,
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {"id": "2", "enabled": True, "type": "terms", "schema": "segment",
         "params": {
             "field": "Detect Name (custom).keyword", "size": 10,
             "order": "desc", "orderBy": "1", "otherBucket": False,
         }},
    ]
    _create_viz("siem-top-detect-names", "Top Detections", "histogram", params, aggs)


def create_ioc_table() -> None:
    """IOC watchlist — type + value with counts, for hunt pivot.

    Limits to 25 rows to stay scannable; analyst sorts by count to find the
    noisiest indicators first, then clicks to filter the dashboard.
    """
    params = {
        "perPage": 25,
        "showPartialRows": False,
        "showMetricsAtAllLevels": False,
        "sort": {"columnIndex": 2, "direction": "desc"},
        "showTotal": False,
        "totalFunc": "sum",
        "percentageCol": "",
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {"id": "2", "enabled": True, "type": "terms", "schema": "bucket",
         "params": {"field": "IOC Type (custom).keyword", "size": 8,
                    "order": "desc", "orderBy": "1", "otherBucket": False,
                    "customLabel": "Tipo"}},
        {"id": "3", "enabled": True, "type": "terms", "schema": "bucket",
         "params": {"field": "IOC Value (custom).keyword", "size": 25,
                    "order": "desc", "orderBy": "1", "otherBucket": False,
                    "customLabel": "Valor"}},
    ]
    _create_viz(
        "siem-ioc-watchlist",
        "IOC Watchlist (Tipo × Valor)",
        "table",
        params,
        aggs,
        query='_exists_:"IOC Value (custom).keyword"',
    )


def create_process_tree() -> None:
    """Suspicious process tree — Account × Parent × Image correlation.

    The three-level breakdown lets an analyst see a single account spawning
    the same parent → child combo across multiple hosts, which is the textbook
    signal for an exploit kit or lateral-movement script.
    """
    params = {
        "perPage": 25, "showPartialRows": False, "showMetricsAtAllLevels": False,
        "sort": {"columnIndex": 3, "direction": "desc"},
        "showTotal": False, "totalFunc": "sum", "percentageCol": "",
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {"id": "2", "enabled": True, "type": "terms", "schema": "bucket",
         "params": {"field": "Account Name (custom).keyword", "size": 6,
                    "order": "desc", "orderBy": "1", "otherBucket": False,
                    "customLabel": "Conta"}},
        {"id": "3", "enabled": True, "type": "terms", "schema": "bucket",
         "params": {"field": "Parent Image File Name (custom).keyword", "size": 6,
                    "order": "desc", "orderBy": "1", "otherBucket": False,
                    "customLabel": "Processo pai"}},
        {"id": "4", "enabled": True, "type": "terms", "schema": "bucket",
         "params": {"field": "Process Name (custom).keyword", "size": 6,
                    "order": "desc", "orderBy": "1", "otherBucket": False,
                    "customLabel": "Processo filho"}},
    ]
    _create_viz(
        "siem-process-tree",
        "Árvore de Processos Suspeitos",
        "table",
        params,
        aggs,
        query='_exists_:"Process Name (custom).keyword" and _exists_:"Parent Image File Name (custom).keyword"',
    )


def create_sources_by_unique_dests() -> None:
    """Top source IPs ranked by *unique* destinations (cardinality).

    A high-volume source talking to one destination is noisy backup traffic;
    a moderate-volume source talking to 50 unique destinations in an hour is
    a port-scanner or pivot host. This metric surfaces the latter, which the
    other 'top sources' panels (raw count) cannot.
    """
    params = {
        "type": "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{
            "id": "CategoryAxis-1", "type": "category", "position": "left", "show": True,
            "style": {}, "scale": {"type": "linear"}, "labels": {"show": True, "truncate": 60},
            "title": {},
        }],
        "valueAxes": [{
            "id": "ValueAxis-1", "name": "BottomAxis-1", "type": "value", "position": "bottom",
            "show": True, "style": {}, "scale": {"type": "linear", "mode": "normal"},
            "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
            "title": {"text": "Destinos únicos"},
        }],
        "seriesParams": [{
            "show": True, "type": "histogram", "mode": "normal",
            "data": {"label": "Destinos únicos", "id": "1"},
            "valueAxis": "ValueAxis-1",
            "drawLinesBetweenPoints": True, "showCircles": True,
        }],
        "addTooltip": True, "addLegend": False, "legendPosition": "right",
        "times": [], "addTimeMarker": False,
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "cardinality", "schema": "metric",
         "params": {"field": "Destination IP.keyword", "customLabel": "Destinos únicos"}},
        {"id": "2", "enabled": True, "type": "terms", "schema": "segment",
         "params": {"field": "Source IP.keyword", "size": 10,
                    "order": "desc", "orderBy": "1", "otherBucket": False}},
    ]
    _create_viz(
        "siem-sources-unique-dests",
        "Sources por Destinos Únicos (sinal de lateral movement)",
        "histogram", params, aggs,
    )


def create_recent_critical_events() -> None:
    """Recent critical-severity events — last 20 alerts demanding attention."""
    columns = [
        "@timestamp", "Threat Severity (custom)", "Detect Name (custom)",
        "Account Name (custom)", "Source IP", "Destination IP",
        "Process Name (custom)", "Fortinet Message (custom)",
    ]
    searchsource = json.dumps({
        "query": {"language": "kuery",
                  "query": '"Threat Severity (custom).keyword": ("critical" or "high")'},
        "filter": [],
        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
    })
    attrs = {
        "title": "Eventos Críticos Recentes",
        "description": "Severidade crítica ou alta, ordenados por horário decrescente.",
        "columns": columns,
        "sort": [["@timestamp", "desc"]],
        "kibanaSavedObjectMeta": {"searchSourceJSON": searchsource},
    }
    result = _create_saved_object(
        "search", "siem-recent-critical",
        attrs,
        references=[_IDX_REF],
    )
    ok = "id" in result
    print(f"  search/siem-recent-critical: {'✓' if ok else '✗ ' + str(result)[:100]}")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

# (viz_id, panel_ref, x, y, w, h, type)
# Grid is 48 units wide.
# Layout:
#  y=0  h=8  : Severity count table (w=16) | Events over time (w=32)
#  y=8  h=16 : Severity pie (w=16) | Top Src IPs (w=16) | Top Dst IPs (w=16)
#  y=24 h=16 : Top Dst Ports (w=16) | Heatmap (w=32)
#  y=40 h=14 : Countries donut (w=16) | Fortinet messages (w=32)
#  y=54 h=14 : Top URLs (w=24) | Src→Dst→Port (w=24)
#  y=68 h=14 : Severity over time (w=48)
#  y=82 h=18 : Recent connections Discover (w=48)

PANEL_LAYOUT = [
    # Row 0: 4 severity KPI tiles (Critical | High | Medium | Low) — SOC at-a-glance
    ("siem-kpi-critical",       "ref_0",   0,  0, 12,  8, "visualization"),
    ("siem-kpi-high",           "ref_1",  12,  0, 12,  8, "visualization"),
    ("siem-kpi-medium",         "ref_2",  24,  0, 12,  8, "visualization"),
    ("siem-kpi-low",            "ref_3",  36,  0, 12,  8, "visualization"),

    # Row 1: severity table + events over time
    ("siem-severity-table",     "ref_4",   0,  8, 16,  8, "visualization"),
    ("siem-events-over-time",   "ref_5",  16,  8, 32,  8, "visualization"),

    # Row 2: severity pie + top src IPs + top dst IPs
    ("siem-severity-pie",       "ref_6",   0, 16, 16, 16, "visualization"),
    ("siem-top-src-ips",        "ref_7",  16, 16, 16, 16, "visualization"),
    ("siem-top-dst-ips",        "ref_8",  32, 16, 16, 16, "visualization"),

    # Row 3 (NEW — hunt pivot): Top detections + Top sources by unique dests
    ("siem-top-detect-names",   "ref_9",   0, 32, 24, 14, "visualization"),
    ("siem-sources-unique-dests","ref_10",24, 32, 24, 14, "visualization"),

    # Row 4: top dst ports + heatmap
    ("siem-top-dst-ports",      "ref_11",  0, 46, 16, 16, "visualization"),
    ("siem-heatmap",            "ref_12", 16, 46, 32, 16, "visualization"),

    # Row 5 (NEW — host investigation): IOC watchlist + Process tree
    ("siem-ioc-watchlist",      "ref_13",  0, 62, 24, 18, "visualization"),
    ("siem-process-tree",       "ref_14", 24, 62, 24, 18, "visualization"),

    # Row 6: countries + Fortinet messages
    ("siem-countries-donut",    "ref_15",  0, 80, 16, 14, "visualization"),
    ("siem-fortinet-messages",  "ref_16", 16, 80, 32, 14, "visualization"),

    # Row 7: URLs + src→dst→port
    ("siem-top-urls",           "ref_17",  0, 94, 24, 14, "visualization"),
    ("siem-src-dst-port",       "ref_18", 24, 94, 24, 14, "visualization"),

    # Row 8: severity over time (full width)
    ("siem-severity-over-time", "ref_19",  0,108, 48, 14, "visualization"),

    # Row 9 (NEW): Recent critical events (saved search filtered to critical/high)
    ("siem-recent-critical",    "ref_20",  0,122, 48, 16, "search"),

    # Row 10: recent connections (full investigation table)
    ("siem-recent-connections", "ref_21",  0,138, 48, 18, "search"),
]


def create_dashboard() -> None:
    panels = []
    references = []
    for idx, (viz_id, ref_name, x, y, w, h, vtype) in enumerate(PANEL_LAYOUT):
        panel_index = f"panel_{idx}"
        panels.append({
            "panelIndex": panel_index,
            "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_index},
            "type": vtype,
            "embeddableConfig": {},
            "panelRefName": ref_name,
            "version": VERSION,
        })
        references.append({"type": vtype, "name": ref_name, "id": viz_id})

    attrs = {
        "title": "HIKARI SIEM",
        "description": (
            "SOC SIEM Hikari — KPIs de severidade, eventos no tempo, "
            "top sources/destinos, top detections, IOC watchlist, "
            "árvore de processos suspeitos, sinal de lateral movement "
            "(cardinality), heatmap porta×origem e busca de eventos críticos."
        ),
        "panelsJSON": json.dumps(panels),
        "optionsJSON": json.dumps({
            "useMargins": True,
            "syncColors": False,
            "hidePanelTitles": False,
        }),
        "version": 1,
        "timeRestore": False,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({
                "query": {"language": "kuery", "query": ""},
                "filter": [],
            }),
        },
    }
    result = _create_saved_object("dashboard", "hikari-siem", attrs, references)
    ok = "id" in result
    print(f"  dashboard/hikari-siem: {'✓' if ok else '✗ ' + str(result)[:200]}")


# ---------------------------------------------------------------------------
# Also write NDJSON for offline use / git tracking
# ---------------------------------------------------------------------------


def write_ndjson() -> None:
    """Write a simplified NDJSON as a reference artifact (not for import)."""
    records = []
    # index pattern
    records.append({
        "id": INDEX_ID, "type": "index-pattern",
        "attributes": {"title": INDEX_ID, "timeFieldName": "@timestamp"},
        "references": [],
    })
    # note: full dashboard JSON written by create_dashboard() into Kibana directly
    NDJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NDJSON_PATH.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  NDJSON stub written to {NDJSON_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("Rebuilding Hikari SIEM dashboard via Kibana REST API...")
    print()

    print("1. Index pattern:")
    create_index_pattern()

    print()
    print("2. Visualizations:")
    create_severity_metrics()        # 4 KPI tiles
    create_severity_count_table()
    create_events_over_time()
    create_severity_over_time()
    create_severity_pie()
    create_top_src_ips()
    create_top_dst_ips()
    create_top_detect_names()        # NEW
    create_sources_by_unique_dests() # NEW
    create_top_dst_ports()
    create_heatmap()
    create_ioc_table()               # NEW
    create_process_tree()            # NEW
    create_countries_donut()
    create_fortinet_messages()
    create_top_urls()
    create_src_dst_port_table()
    create_recent_connections()
    create_recent_critical_events()  # NEW

    print()
    print("3. Dashboard:")
    create_dashboard()

    print()
    print("4. NDJSON stub:")
    write_ndjson()

    print()
    print("Done. Refresh Kibana to see the updated dashboard.")


if __name__ == "__main__":
    main()
