"""JSONL exporter for the activity log.

A generator that yields one line of JSON per record, suitable for streaming
to a HTTP response without materialising the whole result set.
"""

from typing import Iterator

from . import queries
from .dto import ResearchFilters


def jsonl_lines(filters: ResearchFilters) -> Iterator[str]:
    for record in queries.iter_all_events(filters):
        yield record.json() + "\n"
