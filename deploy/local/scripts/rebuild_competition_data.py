"""Rebuild the competition index from JSON files attached to active challenges."""

import json
import logging
import os
import sys
import time
from urllib.parse import urlparse

import pymysql
import requests
from confluent_kafka import Producer


INDEX_NAME = "competition1"
UPLOAD_DIRECTORY = "/var/uploads"
LOGGER = logging.getLogger(__name__)


def database_settings() -> dict[str, object]:
    database_url = urlparse(os.environ["DATABASE_URL"])
    return {
        "host": database_url.hostname,
        "port": database_url.port or 3306,
        "user": database_url.username,
        "password": database_url.password,
        "database": database_url.path.removeprefix("/"),
    }


def active_log_locations(connection: pymysql.Connection) -> list[str]:
    query = """
        SELECT DISTINCT hikari_files.location
        FROM hikari_challenges
        JOIN hikari_files ON hikari_files.filename = hikari_challenges.log_filename
        WHERE hikari_challenges.logs_activated = 1
        ORDER BY hikari_files.location
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        return [row[0] for row in cursor.fetchall()]


def event_batches(locations: list[str]) -> list[tuple[str, list[dict[str, object]]]]:
    batches = []
    for location in locations:
        filename = os.path.join(UPLOAD_DIRECTORY, location)
        with open(filename, encoding="utf-8") as source:
            events = json.load(source)
        if not isinstance(events, list) or not all(isinstance(event, dict) for event in events):
            raise ValueError(f"Challenge log must contain a JSON list of objects: {location}")
        batches.append((location, events))
    return batches


def reset_index(elasticsearch_url: str) -> None:
    response = requests.delete(f"{elasticsearch_url}/{INDEX_NAME}", timeout=30)
    if response.status_code not in (200, 404):
        response.raise_for_status()
    response = requests.put(
        f"{elasticsearch_url}/{INDEX_NAME}",
        json={"mappings": {"subobjects": False}},
        timeout=30,
    )
    response.raise_for_status()


def publish_events(batches: list[tuple[str, list[dict[str, object]]]]) -> int:
    producer = Producer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]})
    count = 0
    for _, events in batches:
        for event in events:
            producer.produce(INDEX_NAME, value=json.dumps(event).encode("utf-8"))
            count += 1
            if count % 10000 == 0:
                producer.poll(0)
    remaining = producer.flush(120)
    if remaining:
        raise RuntimeError(f"Kafka producer did not deliver {remaining} events")
    return count


def wait_for_index_count(elasticsearch_url: str, expected_count: int) -> None:
    for _ in range(60):
        response = requests.get(
            f"{elasticsearch_url}/{INDEX_NAME}/_count", timeout=10
        )
        response.raise_for_status()
        if response.json()["count"] == expected_count:
            return
        time.sleep(1)
    raise RuntimeError(
        f"{INDEX_NAME} did not reach {expected_count} indexed events after 60 seconds"
    )


def main() -> int:
    connection = pymysql.connect(**database_settings())
    try:
        locations = active_log_locations(connection)
    finally:
        connection.close()

    batches = event_batches(locations)
    elasticsearch_url = os.environ["ELASTIC_URL"]
    reset_index(elasticsearch_url)
    event_count = publish_events(batches)
    wait_for_index_count(elasticsearch_url, event_count)
    LOGGER.info(
        "Rebuilt %s from %d log files and %d events.",
        INDEX_NAME,
        len(locations),
        event_count,
    )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.exit(main())
