# Base imports
import typing
# Temporal SDK imports
from temporalio.client import Client


# Avoid circular import for type hints
if typing.TYPE_CHECKING:
    from . import BoostApp


async def create_temporal_client_connector(
    app: "BoostApp",
    temporal_endpoint: str = "localhost:7233",
    temporal_namespace: str = "default",
    enable_otlp: bool = True,
) -> Client | None:  # pragma: no cover
    # opentelemetry.context.get_current()
    try:
        client = await Client.connect(
            temporal_endpoint,
            namespace=temporal_namespace,
        )
    except RuntimeError:
        app.logger.error(
            "Cannot coonect with Temporal server",
            temporal_endpoint=temporal_endpoint,
            temporal_namespace=temporal_namespace
        )
        client = None
    return client
