# Base imports
import typing
# Temporal SDK imports
from temporalio.client import Client
# Local imports
from .opentelemetry import TracingInterceptor
from .schemas import BoostOTLPConfig


# Avoid circular import for type hints
if typing.TYPE_CHECKING:
    from . import BoostApp


async def create_temporal_client_connector(
    app: "BoostApp",
    temporal_endpoint: str = "localhost:7233",
    temporal_namespace: str = "default",
    otlp_config: BoostOTLPConfig | None = None,
) -> Client | None:  # pragma: no cover

    interceptors: list = []

    if app.otlp_config:
        interceptors.append(TracingInterceptor(tracer=app.tracer))

    try:
        client = await Client.connect(
            temporal_endpoint,
            namespace=temporal_namespace,
        )
    except RuntimeError:
        app.logger.error(
            "Cannot connect with Temporal server",
            temporal_endpoint=temporal_endpoint,
            temporal_namespace=temporal_namespace
        )
        client = None
    return client
