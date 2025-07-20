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
        if self._metrics is None and self._prometheus_bind_address is not None:
            self._metrics = PrometheusConfig(
                bind_address=self._prometheus_bind_address,
                counters_total_suffix=self._prometheus_counters_total_suffix or False,
                unit_suffix=self._prometheus_unit_suffix or False,
                durations_as_seconds=self._prometheus_durations_as_seconds or False,
            )

        telemetry_config = TelemetryConfig(
            logging=self._logging,
            metrics=self._metrics,
            global_tags=self._global_tags,
            attach_service_name=self._attach_service_name,
            metric_prefix=self._metric_prefix,
        )
        try:
            runtime = Runtime(telemetry=telemetry_config)
            if self._prometheus_bind_address:
                process_id = multiprocessing.current_process().name
                logger.info(f"Process {process_id}: Metrics server bound to {self._prometheus_bind_address}")
            return runtime
        except ValueError as err:
            err_msg = str(err)
            if "Address already in use" in err_msg and self._prometheus_bind_address:
                _, port_str = self._prometheus_bind_address.split(":")
                process_id = multiprocessing.current_process().name
                logger.warning(
                    f"Process {process_id}: Prometheus exporter port[{port_str}] is already in use. "
                    "Disabling metrics for this process",
                )
                telemetry_config_no_metrics = TelemetryConfig()
                return Runtime(telemetry=telemetry_config_no_metrics)
            raise
