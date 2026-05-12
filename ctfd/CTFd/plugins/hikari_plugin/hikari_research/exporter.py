"""JSONL exporter for the activity log.

A generator that yields one line of JSON per record, suitable for streaming
to a HTTP response without materialising the whole result set.
"""

from typing import Iterator

from . import queries


def jsonl_lines() -> Iterator[str]:
    for record in queries.iter_all_events():
        yield record.json() + "\n"
