# Temporal SDK imports
from temporalio.client import Client


async def create_temporal_client_connector(
    temporal_endpoint: str = "localhost:7233",
    temporal_namespace: str = "default",
    enable_otlp: bool = True,
) -> Client:  # pragma: no cover
    # opentelemetry.context.get_current()

    return await Client.connect(
        temporal_endpoint,
        namespace=temporal_namespace,
    )
