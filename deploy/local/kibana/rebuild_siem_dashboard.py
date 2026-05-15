"""Generate the complete Hikari SIEM dashboard NDJSON for Kibana 8.19.

This script produces hikari-siem.ndjson from scratch, replacing every
legacy visualization type (metric, line, area) with supported equivalents:
  - TSVB in metric mode for KPI severity tiles
  - timelion for the events-over-time time series
  - pie, histogram, heatmap, table, search — all supported in Kibana 8.19

Run from the repo root:
    python deploy/local/kibana/rebuild_siem_dashboard.py
"""

import json
import sys
from pathlib import Path


NDJSON = Path("deploy/local/kibana/hikari-siem.ndjson")
INDEX_ID = "competition1"
VERSION = "8.19.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _searchsource(query: str = "*") -> str:
    return json.dumps({
        "query": {"language": "kuery", "query": query},
        "filter": [],
        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
    })


def _index_ref(name: str) -> dict:
    return {"type": "index-pattern", "name": name, "id": INDEX_ID}


def _vis_record(
    vid: str,
    title: str,
    vis_type: str,
    vis_params: dict,
    aggs: list,
    query: str = "",
    description: str = "",
) -> dict:
    visstate = {"title": title, "type": vis_type, "params": vis_params, "aggs": aggs}
    searchsource = json.dumps({
        "query": {"language": "kuery", "query": query},
        "filter": [],
        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
    })
    return {
        "id": vid,
        "type": "visualization",
        "attributes": {
            "title": title,
            "description": description,
            "visState": json.dumps(visstate),
            "uiStateJSON": "{}",
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": searchsource},
        },
        "references": [_index_ref("kibanaSavedObjectMeta.searchSourceJSON.index")],
    }


# ---------------------------------------------------------------------------
# Index-pattern
# ---------------------------------------------------------------------------

def build_index_pattern() -> dict:
    return {
        "id": INDEX_ID,
        "type": "index-pattern",
        "attributes": {
            "title": INDEX_ID,
            "timeFieldName": "@timestamp",
        },
        "references": [],
    }


# ---------------------------------------------------------------------------
# Row 1: TSVB metric tiles (KPI severity counts)
# ---------------------------------------------------------------------------

SEVERITY_TILES = [
    ("tsvb-metric-critical", "Eventos Críticos", "critical", "#dc2626"),
    ("tsvb-metric-high",     "Eventos Altos",    "high",     "#f97316"),
    ("tsvb-metric-medium",   "Eventos Médios",   "medium",   "#eab308"),
    ("tsvb-metric-low",      "Eventos Baixos",   "low",      "#22c55e"),
]

# Legacy metric saved-objects kept as paper trail (not embedded in dashboard)
LEGACY_METRIC_TILES = [
    ("low-events-metric",      "Eventos Low",      "low",      "#22c55e"),
    ("medium-events-metric",   "Eventos Medium",   "medium",   "#eab308"),
    ("high-events-metric",     "Eventos High",     "high",     "#f97316"),
    ("critical-events-metric", "Eventos Critical", "critical", "#dc2626"),
]


def _tsvb_metric(vid: str, title: str, severity: str, color: str) -> dict:
    """Build a TSVB visualization in metric mode — works in Kibana 8.19."""
    params = {
        "type": "metric",
        "time_range_mode": "entire_time_range",
        "series": [{
            "id": "series1",
            "label": title,
            "color": color,
            "metrics": [{"id": "m1", "type": "count"}],
            "filter": {
                "query": f'"Threat Severity (custom)":"{severity}"',
                "language": "kuery",
            },
            "split_mode": "everything",
            "line_width": 1,
            "point_size": 1,
            "fill": 0.5,
            "stacked": "none",
            "separate_axis": 0,
            "axis_position": "right",
            "formatter": "number",
            "value_template": "{{value}}",
            "override_index_pattern": 0,
            "series_drop_last_bucket": 0,
        }],
        "drop_last_bucket": 0,
        "filter": {"query": "", "language": "kuery"},
        "annotations": [],
        "axis_formatter": "number",
        "axis_scale": "normal",
        "axis_position": "left",
        "axis_min": "",
        "axis_max": "",
        "show_legend": 0,
        "show_grid": 1,
        "tooltip_mode": "show_all",
        "time_field": "@timestamp",
        "index_pattern_ref_name": "tsvb_index",
        "use_kibana_indexes": True,
    }
    rec = {
        "id": vid,
        "type": "visualization",
        "attributes": {
            "title": title,
            "description": f"Total de eventos com severidade {severity}.",
            "visState": json.dumps({"title": title, "type": "tsvb", "params": params, "aggs": []}),
            "uiStateJSON": "{}",
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})},
        },
        "references": [{"type": "index-pattern", "name": "tsvb_index", "id": INDEX_ID}],
    }
    return rec


def _legacy_metric_record(vid: str, title: str, severity: str, color: str) -> dict:
    """Legacy metric saved-object preserved as a paper trail."""
    visstate = {
        "title": title,
        "type": "metric",
        "params": {
            "handleNoResults": True,
            "metric": {
                "percentageMode": False,
                "useRanges": False,
                "labels": {"show": True},
                "invertColors": False,
                "style": {
                    "bgFill": color,
                    "bgColor": False,
                    "labelColor": False,
                    "subText": severity,
                    "fontSize": 52,
                },
            },
        },
        "aggs": [{"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}}],
    }
    searchsource = json.dumps({
        "query": {"language": "kuery", "query": f'"Threat Severity (custom)":"{severity}"'},
        "filter": [],
        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
    })
    return {
        "id": vid,
        "type": "visualization",
        "attributes": {
            "title": title,
            "description": f"Total de eventos com severidade {severity}.",
            "visState": json.dumps(visstate),
            "uiStateJSON": "{}",
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": searchsource},
        },
        "references": [_index_ref("kibanaSavedObjectMeta.searchSourceJSON.index")],
    }


# ---------------------------------------------------------------------------
# Row 2: timelion events over time
# ---------------------------------------------------------------------------

def build_events_over_time() -> dict:
    params = {
        "expression": (
            ".es(index=competition1,timefield=@timestamp,q='*')"
            ".label('Eventos por hora')"
            ".color(#10b981)"
            ".lines(fill=1,width=2)"
        ),
        "interval": "auto",
    }
    return _vis_record(
        "events-over-time-timelion",
        "Eventos por Hora",
        "timelion",
        params,
        [],
        description="Série temporal de eventos de rede por hora.",
    )


# ---------------------------------------------------------------------------
# Row 3: Pie + 2 bar charts
# ---------------------------------------------------------------------------

def build_severity_pie() -> dict:
    params = {
        "type": "pie",
        "addTooltip": True,
        "addLegend": True,
        "legendPosition": "right",
        "isDonut": False,
        "labels": {"show": True, "values": True, "last_level": True, "truncate": 100},
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "segment",
            "params": {
                "field": "Threat Severity (custom)", "size": 10,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
    ]
    return _vis_record(
        "threat-severity-distribution-pie",
        "Distribuição de Severidade",
        "pie", params, aggs,
        description="Proporção de eventos por nível de severidade.",
    )


def build_top_source_ips() -> dict:
    params = {
        "type": "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{"id": "x", "type": "category", "position": "left",
                          "show": True, "style": {},
                          "scale": {"type": "linear"}, "labels": {"show": True, "truncate": 100},
                          "title": {}}],
        "valueAxes": [{"id": "y", "name": "LeftAxis-1", "type": "value", "position": "bottom",
                       "show": True, "style": {},
                       "scale": {"type": "linear", "mode": "normal"},
                       "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                       "title": {"text": "Contagem"}}],
        "seriesParams": [{"show": True, "type": "histogram", "mode": "stacked",
                          "data": {"label": "Contagem", "id": "1"},
                          "valueAxis": "y", "drawLinesBetweenPoints": True,
                          "showCircles": True}],
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
            "params": {
                "field": "Source IP", "size": 10,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
    ]
    return _vis_record(
        "top-source-ips-bar",
        "Top IPs de Origem",
        "histogram", params, aggs,
        description="IPs de origem com maior número de eventos.",
    )


def build_top_dest_ips() -> dict:
    params = {
        "type": "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{"id": "x", "type": "category", "position": "left",
                          "show": True, "style": {},
                          "scale": {"type": "linear"}, "labels": {"show": True, "truncate": 100},
                          "title": {}}],
        "valueAxes": [{"id": "y", "name": "LeftAxis-1", "type": "value", "position": "bottom",
                       "show": True, "style": {},
                       "scale": {"type": "linear", "mode": "normal"},
                       "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                       "title": {"text": "Contagem"}}],
        "seriesParams": [{"show": True, "type": "histogram", "mode": "stacked",
                          "data": {"label": "Contagem", "id": "1"},
                          "valueAxis": "y", "drawLinesBetweenPoints": True,
                          "showCircles": True}],
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
            "params": {
                "field": "Destination IP", "size": 10,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
    ]
    return _vis_record(
        "top-destination-ips-bar",
        "Top IPs de Destino",
        "histogram", params, aggs,
        description="IPs de destino com maior número de eventos.",
    )


# ---------------------------------------------------------------------------
# Row 4: Destination ports bar + heatmap
# ---------------------------------------------------------------------------

def build_top_dest_ports_bar() -> dict:
    params = {
        "type": "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{"id": "x", "type": "category", "position": "left",
                          "show": True, "style": {},
                          "scale": {"type": "linear"}, "labels": {"show": True, "truncate": 100},
                          "title": {}}],
        "valueAxes": [{"id": "y", "name": "LeftAxis-1", "type": "value", "position": "bottom",
                       "show": True, "style": {},
                       "scale": {"type": "linear", "mode": "normal"},
                       "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                       "title": {"text": "Contagem"}}],
        "seriesParams": [{"show": True, "type": "histogram", "mode": "stacked",
                          "data": {"label": "Contagem", "id": "1"},
                          "valueAxis": "y", "drawLinesBetweenPoints": True,
                          "showCircles": True}],
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
            "params": {
                "field": "Destination Port", "size": 15,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
    ]
    return _vis_record(
        "top-destination-ports-bar",
        "Top Portas de Destino",
        "histogram", params, aggs,
        description="Portas de destino mais ativas.",
    )


def build_heatmap() -> dict:
    params = {
        "type": "heatmap",
        "addTooltip": True,
        "addLegend": True,
        "enableHover": False,
        "legendPosition": "right",
        "times": [],
        "colorsNumber": 4,
        "colorSchema": "Blues",
        "setColorRange": False,
        "colorsRange": [],
        "invertColors": False,
        "percentageMode": False,
        "valueAxes": [{"show": False, "id": "ValueAxis-1", "type": "value",
                       "scale": {"type": "linear", "defaultYExtents": False},
                       "labels": {"show": False, "rotate": 0, "overwriteColor": False, "color": "black"}}],
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "segment",
            "params": {
                "field": "Destination Port", "size": 12,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
        {
            "id": "3", "enabled": True, "type": "terms", "schema": "group",
            "params": {
                "field": "Source IP", "size": 10,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
    ]
    return _vis_record(
        "heatmap-port-x-source",
        "Heatmap Porta × Origem",
        "heatmap", params, aggs,
        description="Densidade de eventos por porta de destino e IP de origem.",
    )


# ---------------------------------------------------------------------------
# Row 5: Countries donut + Fortinet messages table
# ---------------------------------------------------------------------------

def build_countries_donut() -> dict:
    params = {
        "type": "pie",
        "addTooltip": True,
        "addLegend": True,
        "legendPosition": "right",
        "isDonut": True,
        "labels": {"show": True, "values": True, "last_level": True, "truncate": 100},
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "segment",
            "params": {
                "field": "destination.geo.country_name", "size": 10,
                "order": "desc", "orderBy": "1", "otherBucket": True,
            },
        },
    ]
    return _vis_record(
        "top-destination-countries-donut",
        "Top Países de Destino",
        "pie", params, aggs,
        description="Distribuição geográfica dos destinos de rede.",
    )


def build_fortinet_messages_table() -> dict:
    params = {
        "perPage": 10,
        "showPartialRows": False,
        "showMetricsAtAllLevels": False,
        "sort": {"columnIndex": None, "direction": None},
        "showTotal": False,
        "totalFunc": "sum",
        "percentageCol": "",
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {
                "field": "Fortinet Message (custom)", "size": 15,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
    ]
    return _vis_record(
        "top-fortinet-messages-table",
        "Top Mensagens Fortinet",
        "table", params, aggs,
        description="Mensagens de log Fortinet mais frequentes.",
    )


# ---------------------------------------------------------------------------
# Row 6: Top URLs + Top Src→Dst→Port table
# ---------------------------------------------------------------------------

def build_top_urls_table() -> dict:
    params = {
        "perPage": 10,
        "showPartialRows": False,
        "showMetricsAtAllLevels": False,
        "sort": {"columnIndex": None, "direction": None},
        "showTotal": False,
        "totalFunc": "sum",
        "percentageCol": "",
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {
                "field": "url.original", "size": 15,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
    ]
    return _vis_record(
        "top-urls-table",
        "Top URLs Acessadas",
        "table", params, aggs,
        description="URLs mais acessadas nos eventos de rede.",
    )


def build_src_dst_port_table() -> dict:
    params = {
        "perPage": 10,
        "showPartialRows": False,
        "showMetricsAtAllLevels": False,
        "sort": {"columnIndex": None, "direction": None},
        "showTotal": False,
        "totalFunc": "sum",
        "percentageCol": "",
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {
                "field": "Source IP", "size": 8,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
        {
            "id": "3", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {
                "field": "Destination IP", "size": 5,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
        {
            "id": "4", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {
                "field": "Destination Port", "size": 5,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
    ]
    return _vis_record(
        "top-src-dst-port-table",
        "Top Origem → Destino → Porta",
        "table", params, aggs,
        description="Combinações mais frequentes de origem, destino e porta.",
    )


# ---------------------------------------------------------------------------
# Additional visualizations (kept from original set for dashboard richness)
# ---------------------------------------------------------------------------

def build_severity_count_table() -> dict:
    params = {
        "perPage": 10,
        "showPartialRows": False,
        "showMetricsAtAllLevels": False,
        "sort": {"columnIndex": None, "direction": None},
        "showTotal": False,
        "totalFunc": "sum",
        "percentageCol": "",
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {
                "field": "Threat Severity (custom)", "size": 10,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
    ]
    return _vis_record(
        "severity-count-table",
        "Contagem por Severidade",
        "table", params, aggs,
        description="Tabela de contagem de eventos por nível de severidade.",
    )


def build_top_services_table() -> dict:
    params = {
        "perPage": 10,
        "showPartialRows": False,
        "showMetricsAtAllLevels": False,
        "sort": {"columnIndex": None, "direction": None},
        "showTotal": False,
        "totalFunc": "sum",
        "percentageCol": "",
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {
                "field": "network.transport", "size": 10,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
    ]
    return _vis_record(
        "top-services-table",
        "Top Protocolos de Transporte",
        "table", params, aggs,
        description="Protocolos de rede mais frequentes.",
    )


def build_top_dest_ports_table() -> dict:
    params = {
        "perPage": 10,
        "showPartialRows": False,
        "showMetricsAtAllLevels": False,
        "sort": {"columnIndex": None, "direction": None},
        "showTotal": False,
        "totalFunc": "sum",
        "percentageCol": "",
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {
                "field": "Destination Port", "size": 20,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
    ]
    return _vis_record(
        "top-destination-ports-table",
        "Top Portas de Destino (tabela)",
        "table", params, aggs,
        description="Tabela detalhada das portas de destino mais ativas.",
    )


def build_top_sources_unique_dests() -> dict:
    params = {
        "type": "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{"id": "x", "type": "category", "position": "left",
                          "show": True, "style": {},
                          "scale": {"type": "linear"}, "labels": {"show": True, "truncate": 100},
                          "title": {}}],
        "valueAxes": [{"id": "y", "name": "LeftAxis-1", "type": "value", "position": "bottom",
                       "show": True, "style": {},
                       "scale": {"type": "linear", "mode": "normal"},
                       "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                       "title": {"text": "Destinos únicos"}}],
        "seriesParams": [{"show": True, "type": "histogram", "mode": "stacked",
                          "data": {"label": "Destinos únicos", "id": "1"},
                          "valueAxis": "y", "drawLinesBetweenPoints": True,
                          "showCircles": True}],
        "addTooltip": True,
        "addLegend": False,
        "legendPosition": "right",
        "times": [],
        "addTimeMarker": False,
    }
    aggs = [
        {
            "id": "1", "enabled": True, "type": "cardinality", "schema": "metric",
            "params": {"field": "Destination IP"},
        },
        {
            "id": "2", "enabled": True, "type": "terms", "schema": "bucket",
            "params": {
                "field": "Source IP", "size": 10,
                "order": "desc", "orderBy": "1", "otherBucket": False,
            },
        },
    ]
    return _vis_record(
        "top-sources-unique-dests",
        "Origens com mais Destinos Únicos",
        "histogram", params, aggs,
        description="IPs de origem que alcançam maior número de destinos distintos.",
    )


# ---------------------------------------------------------------------------
# Discover (search) saved object
# ---------------------------------------------------------------------------

def build_recent_connections() -> dict:
    columns = [
        "@timestamp", "Source IP", "Destination IP", "Destination Port",
        "network.transport", "Threat Severity (custom)", "Fortinet Message (custom)",
    ]
    searchsource = json.dumps({
        "query": {"language": "kuery", "query": ""},
        "filter": [],
        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
        "highlight": {"pre_tags": ["@kibana-highlighted-field@"],
                      "post_tags": ["@/kibana-highlighted-field@"],
                      "fields": {"*": {}}, "fragment_size": 2147483647},
    })
    return {
        "id": "recent-network-connections",
        "type": "search",
        "attributes": {
            "title": "Conexões de Rede Recentes",
            "description": "Eventos de rede mais recentes para investigação no Discover.",
            "columns": columns,
            "sort": [["@timestamp", "desc"]],
            "kibanaSavedObjectMeta": {"searchSourceJSON": searchsource},
        },
        "references": [_index_ref("kibanaSavedObjectMeta.searchSourceJSON.index")],
    }


# ---------------------------------------------------------------------------
# Dashboard panels layout
# ---------------------------------------------------------------------------
# Grid: 48 units wide. Controls row at y=0 h=5. All other rows shifted +5.
#
# Row 0  (y=0,  h=5):  Controls panel
# Row 1  (y=5,  h=8):  4 TSVB metric tiles (w=12 each)
# Row 2  (y=13, h=16): Events over time (w=48)
# Row 3  (y=29, h=16): Severity pie (w=16) + Top Src IPs (w=16) + Top Dst IPs (w=16)
# Row 4  (y=45, h=16): Top Dst Ports bar (w=16) + Heatmap (w=32)
# Row 5  (y=61, h=14): Countries donut (w=16) + Fortinet messages table (w=32)
# Row 6  (y=75, h=14): Top URLs table (w=24) + Src→Dst→Port table (w=24)
# Row 7  (y=89, h=18): Recent connections Discover (w=48)
# ---------------------------------------------------------------------------

CONTROLS_PANEL = {
    "panelIndex": "panel_controls",
    "version": VERSION,
    "gridData": {"x": 0, "y": 0, "w": 48, "h": 5, "i": "panel_controls"},
    "type": "control_group",
    "embeddableConfig": {
        "controlStyle": "onlyField",
        "chainingSystem": "HIERARCHICAL",
        "ignoreParentSettings": {
            "ignoreFilters": False,
            "ignoreQuery": False,
            "ignoreTimerange": False,
            "ignoreValidations": False,
        },
        "controls": [
            {
                "type": "optionsListControl",
                "order": 0,
                "id": "ctrl_severity",
                "width": "medium",
                "grow": True,
                "fieldName": "Threat Severity (custom)",
                "dataViewId": INDEX_ID,
                "title": "Severidade",
                "selectedOptions": [],
                "runPastTimeout": False,
                "singleSelect": False,
                "existsSelected": False,
                "sort": {"by": "_key", "direction": "asc"},
            },
            {
                "type": "optionsListControl",
                "order": 1,
                "id": "ctrl_proto",
                "width": "medium",
                "grow": True,
                "fieldName": "network.transport",
                "dataViewId": INDEX_ID,
                "title": "Protocolo",
                "selectedOptions": [],
                "runPastTimeout": False,
                "singleSelect": False,
                "existsSelected": False,
            },
            {
                "type": "rangeSliderControl",
                "order": 2,
                "id": "ctrl_port",
                "width": "medium",
                "grow": True,
                "fieldName": "destination.port",
                "dataViewId": INDEX_ID,
                "title": "Porta de destino",
                "step": 1,
            },
        ],
    },
}

# (panel_id, viz_id, viz_type, x, y, w, h)
PANEL_LAYOUT = [
    # Row 1 — TSVB KPI tiles
    ("panel_critical", "tsvb-metric-critical", "visualization",  0,  5, 12,  8),
    ("panel_high",     "tsvb-metric-high",     "visualization", 12,  5, 12,  8),
    ("panel_medium",   "tsvb-metric-medium",   "visualization", 24,  5, 12,  8),
    ("panel_low",      "tsvb-metric-low",      "visualization", 36,  5, 12,  8),
    # Row 2 — Events over time
    ("panel_timeline", "events-over-time-timelion", "visualization", 0, 13, 48, 16),
    # Row 3 — Pie + bars
    ("panel_severity_pie", "threat-severity-distribution-pie", "visualization",  0, 29, 16, 16),
    ("panel_src_ips",      "top-source-ips-bar",               "visualization", 16, 29, 16, 16),
    ("panel_dst_ips",      "top-destination-ips-bar",          "visualization", 32, 29, 16, 16),
    # Row 4 — Ports bar + heatmap
    ("panel_dst_ports_bar", "top-destination-ports-bar", "visualization",  0, 45, 16, 16),
    ("panel_heatmap",       "heatmap-port-x-source",     "visualization", 16, 45, 32, 16),
    # Row 5 — Countries donut + Fortinet table
    ("panel_countries", "top-destination-countries-donut",  "visualization",  0, 61, 16, 14),
    ("panel_messages",  "top-fortinet-messages-table",      "visualization", 16, 61, 32, 14),
    # Row 6 — URLs + Src→Dst→Port
    ("panel_urls",         "top-urls-table",         "visualization",  0, 75, 24, 14),
    ("panel_src_dst_port", "top-src-dst-port-table", "visualization", 24, 75, 24, 14),
    # Row 7 — Discover
    ("panel_recent", "recent-network-connections", "search", 0, 89, 48, 18),
]


def build_dashboard(panels_json: str, references: list) -> dict:
    return {
        "id": "hikari-siem",
        "type": "dashboard",
        "attributes": {
            "title": "HIKARI SIEM",
            "description": (
                "Painel de operações de segurança — SOC SIEM Hikari. "
                "Severidade, eventos por hora, IPs, portas, heatmap, URLs e "
                "conexões recentes. Use os filtros no topo para pivotar por "
                "severidade, protocolo ou porta."
            ),
            "panelsJSON": panels_json,
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
        },
        "references": references,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    records: list[dict] = []

    # 1. Index pattern
    records.append(build_index_pattern())

    # 2. Legacy metric saved-objects (paper trail — not embedded in dashboard)
    for vid, title, severity, color in LEGACY_METRIC_TILES:
        records.append(_legacy_metric_record(vid, title, severity, color))

    # 3. TSVB metric tiles
    for vid, title, severity, color in SEVERITY_TILES:
        records.append(_tsvb_metric(vid, title, severity, color))

    # 4. Visualizations
    records.append(build_events_over_time())
    records.append(build_severity_pie())
    records.append(build_top_source_ips())
    records.append(build_top_dest_ips())
    records.append(build_top_dest_ports_bar())
    records.append(build_heatmap())
    records.append(build_countries_donut())
    records.append(build_fortinet_messages_table())
    records.append(build_top_urls_table())
    records.append(build_src_dst_port_table())
    records.append(build_severity_count_table())
    records.append(build_top_services_table())
    records.append(build_top_dest_ports_table())
    records.append(build_top_sources_unique_dests())

    # 5. Discover saved search
    records.append(build_recent_connections())

    # 6. Build dashboard panels and references
    panels = [CONTROLS_PANEL]
    references = []
    for pid, vid, vtype, x, y, w, h in PANEL_LAYOUT:
        panels.append({
            "panelIndex": pid,
            "gridData": {"x": x, "y": y, "w": w, "h": h, "i": pid},
            "type": vtype,
            "embeddableConfig": {},
            "panelRefName": pid,
            "version": VERSION,
        })
        references.append({"type": vtype, "name": pid, "id": vid})

    records.append(build_dashboard(json.dumps(panels), references))

    # 7. Write NDJSON
    NDJSON.parent.mkdir(parents=True, exist_ok=True)
    with NDJSON.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    total_panels = len(panels)
    sys.stderr.write(
        f"hikari-siem.ndjson written: {len(records)} records, "
        f"{total_panels} panels "
        f"(1 control_group + {total_panels - 1} visualization/search panels)\n"
    )


if __name__ == "__main__":
    main()
