"""Every value this plugin reads from its environment, in one place.

Settings used to be read wherever they were needed, which let one variable
carry two different defaults — ELASTIC_URL pointed at a host that does not
exist in one module and at the real service in another — and spread the same
truthiness rule across separate copies. Reading them once, here, means a
deployment has a single list of what it can configure.
"""

import os
from functools import lru_cache

from pydantic import BaseModel


TRUE_VALUES = frozenset({"true", "1", "yes", "on"})

_TEXT_SETTINGS = {
    "elastic_url": "ELASTIC_URL",
    "elastic_username": "ELASTIC_USERNAME",
    "elastic_password": "ELASTIC_PASSWORD",
    "kibana_url": "KIBANA_URL",
    "kibana_internal_url": "KIBANA_INTERNAL_URL",
    "kibana_username": "KIBANA_USERNAME",
    "kibana_password": "KIBANA_PASSWORD",
    "kibana_base_path": "HIKARI_KIBANA_BASE_PATH",
    "kafka_bootstrap_servers": "KAFKA_BOOTSTRAP_SERVERS",
    "kafka_sasl_mechanism": "KAFKA_SASL_MECHANISM",
    "google_client_id": "HIKARI_GOOGLE_CLIENT_ID",
    "google_client_secret": "HIKARI_GOOGLE_CLIENT_SECRET",
    "oauth_redirect_base": "HIKARI_OAUTH_REDIRECT_BASE",
    "time_zone": "HIKARI_TIME_ZONE",
    "competition_key": "HIKARI_COMPETITION_KEY",
}

_FLAG_SETTINGS = {
    "kafka_use_sasl": "KAFKA_USE_SASL",
    "kibana_provisioning": "HIKARI_KIBANA_PROVISIONING",
    "kibana_export_blocked": "HIKARI_KIBANA_BLOCK_EXPORT",
}


class HikariSettings(BaseModel):
    """What a deployment supplies, with the defaults a local stack relies on."""

    elastic_url: str = "http://elasticsearch:9200"
    elastic_username: str = "elastic"
    elastic_password: str = ""
    kibana_url: str = "http://kibana:5601"
    kibana_internal_url: str = "http://kibana:5601"
    kibana_username: str = "elastic"
    kibana_password: str = ""
    kibana_base_path: str = "/hikari/kibana"
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_sasl_mechanism: str = "SCRAM-SHA-512"
    kafka_use_sasl: bool = False
    kibana_provisioning: bool = False
    # Bulk export turns hunting into a file an assistant can read. Blocking it
    # is the default; a deployment that wants it back says so explicitly.
    kibana_export_blocked: bool = True
    google_client_id: str = ""
    google_client_secret: str = ""
    oauth_redirect_base: str = ""
    time_zone: str = "America/Sao_Paulo"
    competition_key: str = "local"

    class Config:
        allow_mutation = False


def _provided_text() -> dict:
    """Collect the text settings the environment actually defines."""
    return {
        field: os.environ[name].strip()
        for field, name in _TEXT_SETTINGS.items()
        if os.environ.get(name, "").strip()
    }


def _provided_flags() -> dict:
    """Read only the flags the environment actually defines.

    A flag absent from the environment has to fall through to the default
    declared on the model. Reading every name unconditionally turned every
    absent flag into False and made a default of True impossible to express.
    """
    return {
        field: os.environ[name].strip().lower() in TRUE_VALUES
        for field, name in _FLAG_SETTINGS.items()
        if os.environ.get(name, "").strip()
    }


@lru_cache(maxsize=1)
def settings() -> HikariSettings:
    """Return the settings of this deployment, read once."""
    return HikariSettings(**_provided_text(), **_provided_flags())
