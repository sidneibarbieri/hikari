"""Forensic classifier for Kibana proxy traffic.

Extracts structured facts from a Kibana request so the activity log carries
analysable signal, not just a hash of the body. The classifier is a pure
function: given a path, method and body, return a ``KibanaQueryFacts`` DTO.
No HTTP, no DB, no globals.

The Kibana surface accepts several encodings of essentially the same idea
(search a dataset, with a query, in a time window). The classifier collapses
that variety into one shape that researchers can group, count and compare
without re-parsing the raw body.
"""

import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


_CONSOLE_PROXY_MARKER = "api/console/proxy"
_INTERNAL_SEARCH_MARKER = "internal/search"
_INTERNAL_BSEARCH_MARKER = "internal/bsearch"
_SAVED_OBJECTS_MARKER = "api/saved_objects"
_DISCOVER_MARKER = "app/discover"
_DASHBOARDS_MARKER = "app/dashboards"
_VISUALIZE_MARKER = "app/visualize"

_INDEX_FIELD_KEYS = ("index", "indices", "indexPattern", "indexPatternId", "index_pattern")
_QUERY_STRING_PATTERN = re.compile(r'"query_string"[^{]*\{[^}]*"query"\s*:\s*"([^"]+)"')
_KQL_QUERY_PATTERN = re.compile(r'"kuery"\s*:\s*"([^"]*)"|"language"\s*:\s*"kuery"[^"]*?"query"\s*:\s*"([^"]*)"')

_FREE_TEXT_LIMIT = 240


class KibanaQueryFacts(BaseModel):
    """Structured view of a Kibana request, suitable for the activity payload."""

    query_kind: str
    indices: List[str] = []
    has_query: bool = False
    has_filters: bool = False
    has_aggs: bool = False
    has_sort: bool = False
    filter_count: int = 0
    must_count: int = 0
    should_count: int = 0
    must_not_count: int = 0
    size: Optional[int] = None
    time_range_field: Optional[str] = None
    time_range_gte: Optional[str] = None
    time_range_lte: Optional[str] = None
    free_text_excerpt: Optional[str] = None


def classify(path: str, method: str, body: bytes) -> KibanaQueryFacts:
    """Return the structured facts for a single Kibana request."""
    normalized = path.strip("/")
    kind = _kind_for(normalized, method)
    facts = KibanaQueryFacts(query_kind=kind)

    decoded = _decode_body(body)
    if decoded is None:
        facts.free_text_excerpt = _free_text_from_raw(body)
        return facts

    _collect_indices(decoded, facts)
    inner_query = _extract_query_block(decoded)
    if inner_query is not None:
        facts.has_query = True
        _collect_bool_counts(inner_query, facts)
        _collect_time_range(inner_query, facts)

    facts.has_filters = _has_key(decoded, "filter") or facts.filter_count > 0
    facts.has_aggs = _has_key(decoded, "aggs") or _has_key(decoded, "aggregations")
    facts.has_sort = _has_key(decoded, "sort")
    facts.size = _first_int(decoded, "size")
    facts.free_text_excerpt = _free_text(decoded, body)
    return facts


def _kind_for(normalized_path: str, method: str) -> str:
    if method == "GET":
        if normalized_path.endswith(_DISCOVER_MARKER) or _DISCOVER_MARKER in normalized_path:
            return "discover_open"
        if _DASHBOARDS_MARKER in normalized_path:
            return "dashboard_open"
        if _VISUALIZE_MARKER in normalized_path:
            return "visualize_open"
        return "browse"
    if _CONSOLE_PROXY_MARKER in normalized_path:
        return "console"
    if _INTERNAL_BSEARCH_MARKER in normalized_path:
        return "bsearch"
    if _INTERNAL_SEARCH_MARKER in normalized_path:
        return "search"
    if _SAVED_OBJECTS_MARKER in normalized_path:
        return "saved_object"
    return "unknown"


def _decode_body(body: bytes) -> Optional[Any]:
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def _collect_indices(decoded: Any, facts: KibanaQueryFacts) -> None:
    found: List[str] = []
    _walk_for_indices(decoded, found)
    seen: Dict[str, None] = {}
    for index in found:
        if index and index not in seen:
            seen[index] = None
    facts.indices = list(seen)


def _walk_for_indices(node: Any, accumulator: List[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _INDEX_FIELD_KEYS:
                _append_indices(value, accumulator)
            else:
                _walk_for_indices(value, accumulator)
    elif isinstance(node, list):
        for item in node:
            _walk_for_indices(item, accumulator)


def _append_indices(value: Any, accumulator: List[str]) -> None:
    if isinstance(value, str):
        accumulator.append(value)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                accumulator.append(item)


def _extract_query_block(decoded: Any) -> Optional[Any]:
    if not isinstance(decoded, (dict, list)):
        return None
    if isinstance(decoded, dict):
        if "query" in decoded:
            return decoded["query"]
        for value in decoded.values():
            inner = _extract_query_block(value)
            if inner is not None:
                return inner
        return None
    for item in decoded:
        inner = _extract_query_block(item)
        if inner is not None:
            return inner
    return None


def _collect_bool_counts(node: Any, facts: KibanaQueryFacts) -> None:
    if isinstance(node, dict):
        bool_clause = node.get("bool")
        if isinstance(bool_clause, dict):
            facts.must_count += _length(bool_clause.get("must"))
            facts.should_count += _length(bool_clause.get("should"))
            facts.must_not_count += _length(bool_clause.get("must_not"))
            facts.filter_count += _length(bool_clause.get("filter"))
        for value in node.values():
            _collect_bool_counts(value, facts)
    elif isinstance(node, list):
        for item in node:
            _collect_bool_counts(item, facts)


def _collect_time_range(node: Any, facts: KibanaQueryFacts) -> None:
    if facts.time_range_field is not None:
        return
    if isinstance(node, dict):
        range_clause = node.get("range")
        if isinstance(range_clause, dict):
            for field, bounds in range_clause.items():
                if not isinstance(bounds, dict):
                    continue
                facts.time_range_field = field
                facts.time_range_gte = _stringify(bounds.get("gte") or bounds.get("gt"))
                facts.time_range_lte = _stringify(bounds.get("lte") or bounds.get("lt"))
                return
        for value in node.values():
            _collect_time_range(value, facts)
    elif isinstance(node, list):
        for item in node:
            _collect_time_range(item, facts)


def _length(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return 1
    return 0


def _has_key(decoded: Any, key: str) -> bool:
    if isinstance(decoded, dict):
        if key in decoded:
            return True
        return any(_has_key(value, key) for value in decoded.values())
    if isinstance(decoded, list):
        return any(_has_key(item, key) for item in decoded)
    return False


def _first_int(decoded: Any, key: str) -> Optional[int]:
    if isinstance(decoded, dict):
        value = decoded.get(key)
        if isinstance(value, int):
            return value
        for inner in decoded.values():
            found = _first_int(inner, key)
            if found is not None:
                return found
    elif isinstance(decoded, list):
        for inner in decoded:
            found = _first_int(inner, key)
            if found is not None:
                return found
    return None


def _free_text(decoded: Any, raw_body: bytes) -> Optional[str]:
    kql = _kql_excerpt(decoded)
    if kql:
        return kql
    return _free_text_from_raw(raw_body)


def _kql_excerpt(decoded: Any) -> Optional[str]:
    if isinstance(decoded, dict):
        kql = decoded.get("kuery")
        if isinstance(kql, str) and kql:
            return _shorten(kql)
        language = decoded.get("language")
        query_value = decoded.get("query")
        if language == "kuery" and isinstance(query_value, str) and query_value:
            return _shorten(query_value)
        for value in decoded.values():
            inner = _kql_excerpt(value)
            if inner is not None:
                return inner
    elif isinstance(decoded, list):
        for value in decoded:
            inner = _kql_excerpt(value)
            if inner is not None:
                return inner
    return None


def _free_text_from_raw(raw_body: bytes) -> Optional[str]:
    if not raw_body:
        return None
    text = raw_body[:4096].decode("utf-8", errors="replace")
    match = _QUERY_STRING_PATTERN.search(text)
    if match:
        return _shorten(match.group(1))
    match = _KQL_QUERY_PATTERN.search(text)
    if match:
        return _shorten(match.group(1) or match.group(2))
    return None


def _stringify(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _shorten(text: str) -> str:
    if len(text) <= _FREE_TEXT_LIMIT:
        return text
    return text[:_FREE_TEXT_LIMIT] + "..."
