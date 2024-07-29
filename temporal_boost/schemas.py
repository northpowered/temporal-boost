# Local imports
from dataclasses import dataclass
from enum import Enum


@dataclass
class BoostOTLPConfig:
    otlp_endpoint: str
    service_name: str | None = None


@dataclass
class ClientConnectorArgs:
    temporal_endpoint: str = "localhost:7233"
    temporal_namespace: str = "default"
    otlp_config: BoostOTLPConfig | None = None


class WorkerType(Enum):
    TEMPORAL = "Temporal"
    ASGI = "ASGI"
    INTERNAL = "Internal"
