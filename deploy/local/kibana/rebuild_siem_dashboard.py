"""Add the four severity metric tiles (Low / Medium / High / Critical)
from dashboard.zip into deploy/local/kibana/hikari-siem.ndjson, and
reflow the dashboard so they appear at the very top — first thing a
SOC analyst sees when opening the dashboard. Idempotent: re-running
overwrites the same panel set without duplicates.
"""

import json
from pathlib import Path

NDJSON = Path("deploy/local/kibana/hikari-siem.ndjson")

# Metric tile definitions — KQL filter per severity, color picked to
# match the Hikari palette (low/medium/high/critical escalating).
TILES = [
    ("low-events-metric", "Eventos Low", "low", "#22c55e"),
    ("medium-events-metric", "Eventos Medium", "medium", "#eab308"),
    ("high-events-metric", "Eventos High", "high", "#f97316"),
    ("critical-events-metric", "Eventos Critical", "critical", "#dc2626"),
]

# Full panel layout. Metric tiles span the top row; everything else
# stays as before. Width grid is 48 columns; 4 tiles of 12 columns each
# fit the whole row.
PANELS = [
    # (panel id, viz id, type, x, y, w, h)
    ("panel_metric_low", "low-events-metric", "visualization", 0, 0, 12, 8),
    ("panel_metric_medium", "medium-events-metric", "visualization", 12, 0, 12, 8),
    ("panel_metric_high", "high-events-metric", "visualization", 24, 0, 12, 8),
    ("panel_metric_critical", "critical-events-metric", "visualization", 36, 0, 12, 8),
    ("panel_severity", "severity-count-table", "visualization", 0, 8, 16, 12),
    ("panel_severity_pie", "threat-severity-distribution-pie", "visualization", 16, 8, 16, 12),
    ("panel_services", "top-services-table", "visualization", 32, 8, 16, 12),
    ("panel_timeline", "events-over-time-line", "visualization", 0, 20, 48, 14),
    ("panel_dest_ports", "top-destination-ports-bar", "visualization", 0, 34, 16, 14),
    ("panel_dest_ips", "top-destination-ips-bar", "visualization", 16, 34, 16, 14),
    ("panel_source_ips", "top-source-ips-bar", "visualization", 32, 34, 16, 14),
    ("panel_countries", "top-destination-countries-donut", "visualization", 0, 48, 16, 14),
    ("panel_heatmap", "heatmap-port-x-source", "visualization", 16, 48, 32, 16),
    ("panel_ports_table", "top-destination-ports-table", "visualization", 0, 64, 24, 14),
    ("panel_messages", "top-fortinet-messages-table", "visualization", 24, 64, 24, 14),
    ("panel_urls", "top-urls-table", "visualization", 0, 78, 24, 14),
    ("panel_recent", "recent-network-connections", "search", 24, 78, 24, 18),
    ("panel_severity_area", "severity-stacked-area", "visualization", 0, 96, 48, 16),
    ("panel_unique_dests", "top-sources-unique-dests", "visualization", 0, 112, 24, 16),
    ("panel_src_dst_port", "top-src-dst-port-table", "visualization", 24, 112, 24, 16),
]


def build_metric_record(vid: str, title: str, severity: str, color: str) -> dict:
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
                    # Match the original dashboard.zip pattern: keep
                    # bgColor=false so the metric value stays readable
                    # against the dark theme. bgFill is recorded as a
                    # palette hint but not painted onto the tile.
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
    searchsource = {
        "query": {
            "language": "kuery",
            "query": f'"Threat Severity (custom)" : "{severity}"',
        },
        "filter": [],
        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
    }
    return {
        "id": vid,
        "type": "visualization",
        "attributes": {
            "title": title,
            "description": f"Total de eventos com severidade {severity}.",
            "visState": json.dumps(visstate),
            "uiStateJSON": "{}",
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(searchsource)},
        },
        "references": [
            {
                "type": "index-pattern",
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                "id": "competition1",
            }
        ],
    }


records = []
with NDJSON.open("r", encoding="utf-8") as handle:
    for line in handle:
        if line.strip():
            records.append(json.loads(line))

# Remove any pre-existing metric tiles so reruns are idempotent.
metric_ids = {vid for vid, *_ in TILES}
records = [r for r in records if r["id"] not in metric_ids]

# Insert the metric records right after the index-pattern so the
# dashboard import order respects dependencies.
index_idx = next(i for i, r in enumerate(records) if r["id"] == "competition1")
new_metrics = [build_metric_record(vid, title, sev, color) for vid, title, sev, color in TILES]
records = records[: index_idx + 1] + new_metrics + records[index_idx + 1:]

# Refresh the dashboard with the new layout.
dashboard = next(r for r in records if r["id"] == "hikari-siem")
panels = []
references = []
for pid, vid, vtype, x, y, w, h in PANELS:
    panels.append({
        "panelIndex": pid,
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": pid},
        "type": vtype,
        "embeddableConfig": {},
        "panelRefName": pid,
    })
    references.append({"type": vtype, "name": pid, "id": vid})
dashboard["attributes"]["panelsJSON"] = json.dumps(panels)
dashboard["references"] = references

with NDJSON.open("w", encoding="utf-8") as handle:
    for r in records:
        handle.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"NDJSON now has {len(records)} records and {len(panels)} panels")
