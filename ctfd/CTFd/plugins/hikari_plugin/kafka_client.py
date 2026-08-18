"""Shared Kafka producer factory for Hikari modules.

A single module-level producer is reused across the plugin to avoid the cost
of repeated TCP handshakes and metadata fetches. Configuration is read from
environment variables only — there are no defaults that hide a misconfigured
deployment from view.
"""

import os
from typing import Dict, Optional

from confluent_kafka import Producer


from CTFd.plugins.hikari_plugin.settings import settings


def build_producer_config() -> Dict[str, str]:
    """Return the librdkafka configuration derived from environment variables."""
    bootstrap_servers = settings().kafka_bootstrap_servers
    config: Dict[str, str] = {"bootstrap.servers": bootstrap_servers}

    if not settings().kafka_use_sasl:
        return config

    config.update({
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": settings().kafka_sasl_mechanism,
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
