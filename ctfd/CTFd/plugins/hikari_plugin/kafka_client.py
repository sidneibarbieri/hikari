"""Shared Kafka producer factory for Hikari modules.

A single module-level producer is reused across the plugin to avoid the cost
of repeated TCP handshakes and metadata fetches. Configuration is read from
environment variables only — there are no defaults that hide a misconfigured
deployment from view.
"""

import os
from typing import Dict, Optional

from confluent_kafka import Producer


_TRUE_VALUES = frozenset({"true", "1", "yes", "on"})


def build_producer_config() -> Dict[str, str]:
    """Return the librdkafka configuration derived from environment variables."""
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    config: Dict[str, str] = {"bootstrap.servers": bootstrap_servers}

    if os.environ.get("KAFKA_USE_SASL", "").lower() not in _TRUE_VALUES:
        return config

    config.update({
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": os.environ.get("KAFKA_SASL_MECHANISM", "SCRAM-SHA-512"),
        "sasl.username": os.environ["KAFKA_SASL_USERNAME"],
        "sasl.password": os.environ["KAFKA_SASL_PASSWORD"],
    })
    return config


_producer: Optional[Producer] = None


def get_producer() -> Producer:
    """Return the process-wide Kafka producer, building it on first use."""
    global _producer
    if _producer is None:
        _producer = Producer(build_producer_config())
    return _producer
