"""Persist an activity record to the database and publish it to Kafka.

These functions do not catch their own exceptions. Callers wrap them at the
boundary with concrete except clauses and log via ``logger.exception`` so the
underlying error is visible in operational logs without crashing the
user-facing request that triggered the record.
"""

from typing import Final

from CTFd.models import db
from CTFd.plugins.hikari_plugin.kafka_client import get_producer

from .dto import ActivityRecord
from .models import HikariActivity


ACTIVITY_TOPIC: Final = "hikari-activity"


def persist(record: ActivityRecord) -> HikariActivity:
    """Write the record to the relational store and return the persisted row."""
    row = HikariActivity(**record.dict())
    db.session.add(row)
    db.session.commit()
    return row


def publish(record: ActivityRecord) -> None:
    """Send the record to the Kafka activity topic. Does not flush."""
    producer = get_producer()
    producer.produce(ACTIVITY_TOPIC, value=record.json().encode("utf-8"))
    producer.poll(0)
