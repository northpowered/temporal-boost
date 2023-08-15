# Local imports
from dataclasses import dataclass


@dataclass
class ClientConnectorArgs:

    temporal_endpoint: str = "localhost:7233"
    temporal_namespace: str = "default"
    enable_otlp: bool = True
