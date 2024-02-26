# Base imports
import typing

# Temporal SDK imports
from temporalio import workflow
from temporalio.client import Client
from temporalio.runtime import (
    PrometheusConfig,
    Runtime,
    TelemetryConfig,
    _default_runtime,
)
from temporalio.converter import DataConverter

# Local imports
from .opentelemetry import TracingInterceptor


# Avoid circular import for type hints
if typing.TYPE_CHECKING:
    from . import BoostApp

with workflow.unsafe.imports_passed_through():

    from .extentions import pydantic_data_converter


async def create_temporal_client_connector(
    app: "BoostApp",
    temporal_endpoint: str = "localhost:7233",
    temporal_namespace: str = "default",
    metrics_endpoint: str | None = None,
) -> Client | None:  # pragma: no cover

    interceptors: list = []

    runtime: Runtime = _default_runtime

    # Check and add OTLP config
    if app.otlp_config:
        interceptors.append(TracingInterceptor(tracer=app.tracer))

    # Check and add metrics exporter
    if metrics_endpoint:
        runtime = Runtime(
            telemetry=TelemetryConfig(
                metrics=PrometheusConfig(bind_address=metrics_endpoint),
            )
        )
    # Check PyDantic usage:
    data_converter: DataConverter = DataConverter.default
    if app.use_pydantic:
        data_converter = pydantic_data_converter

    # Creating Temporal client
    try:
        client = await Client.connect(
            temporal_endpoint,
            namespace=temporal_namespace,
            runtime=runtime,
            data_converter=data_converter,
        )
    except RuntimeError:
        app.logger.error(
            "Cannot connect with Temporal server",
            temporal_endpoint=temporal_endpoint,
            temporal_namespace=temporal_namespace,
        )
        client = None
    return client
