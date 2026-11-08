import logging
import multiprocessing
from collections.abc import Mapping

from temporalio.runtime import (
    LoggingConfig,
    MetricBuffer,
    OpenTelemetryConfig,
    PrometheusConfig,
    Runtime,
    TelemetryConfig,
)

from temporal_boost.temporal import config


logger = logging.getLogger(__name__)


class TemporalRuntimeBuilder:
    """Build an independent SDK runtime, owning its configured metrics exporter.

    Use distinct Prometheus endpoints for concurrent runtimes and scrape each
    endpoint. Runtimes and listening sockets are never shared automatically.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        logging: LoggingConfig | None = None,
        metrics: OpenTelemetryConfig | PrometheusConfig | MetricBuffer | None = None,
        global_tags: Mapping[str, str] | None = None,
        attach_service_name: bool = True,
        metric_prefix: str | None = None,
        prometheus_bind_address: str | None = config.PROMETHEUS_BIND_ADDRESS,
        prometheus_counters_total_suffix: bool | None = config.PROMETHEUS_COUNTERS_TOTAL_SUFFIX,
        prometheus_unit_suffix: bool | None = config.PROMETHEUS_UNIT_SUFFIX,
        prometheus_durations_as_seconds: bool | None = config.PROMETHEUS_DURATIONS_AS_SECONDS,
    ) -> None:
        self._logging = logging or LoggingConfig.default
        self._metrics = metrics

        self._global_tags = global_tags or {}
        self._attach_service_name = attach_service_name
        self._metric_prefix = metric_prefix
        self._prometheus_bind_address = prometheus_bind_address
        self._prometheus_counters_total_suffix = prometheus_counters_total_suffix
        self._prometheus_unit_suffix = prometheus_unit_suffix
        self._prometheus_durations_as_seconds = prometheus_durations_as_seconds

    def build(self) -> Runtime:
        """Create a runtime without degrading telemetry on initialization failure.

        Raises:
            ValueError: If SDK initialization fails, including a metrics bind conflict.
        """
        metrics = self._metrics
        if metrics is None and self._prometheus_bind_address is not None:
            metrics = PrometheusConfig(
                bind_address=self._prometheus_bind_address,
                counters_total_suffix=self._prometheus_counters_total_suffix or False,
                unit_suffix=self._prometheus_unit_suffix or False,
                durations_as_seconds=self._prometheus_durations_as_seconds or False,
            )

        telemetry_config = TelemetryConfig(
            logging=self._logging,
            metrics=metrics,
            global_tags=self._global_tags,
            attach_service_name=self._attach_service_name,
            metric_prefix=self._metric_prefix,
        )
        try:
            runtime = Runtime(telemetry=telemetry_config)
        except ValueError:
            if isinstance(metrics, PrometheusConfig):
                logger.exception(
                    "Process %s: Could not initialize runtime with Prometheus endpoint %s. "
                    "Each runtime needs a distinct endpoint; scrape every worker/process endpoint. "
                    "Refusing to disable telemetry and report incomplete metrics.",
                    multiprocessing.current_process().name,
                    metrics.bind_address,
                )
            raise
        if isinstance(metrics, PrometheusConfig):
            logger.info(
                "Process %s: Prometheus exporter bound to %s",
                multiprocessing.current_process().name,
                metrics.bind_address,
            )
        return runtime
