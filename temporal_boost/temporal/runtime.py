import logging
import socket
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


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        result = sock.connect_ex((host, port))
        return result == 0


def create_runtime(  # noqa: PLR0913
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
) -> Runtime:
    if logging is None:
        logging = LoggingConfig.default
    if global_tags is None:
        global_tags = {}

    if metrics is None and prometheus_bind_address is not None:
        try:
            host, port_str = prometheus_bind_address.split(":")
            port = int(port_str)
        except Exception as exc:
            raise ValueError("Invalid prometheus_bind_address format, expected 'host:port'") from exc

        if is_port_in_use(host, port):
            logger.warning(f"Port {port} on {host} is already in use. Disabling Prometheus metrics.")
            metrics = None
        else:
            metrics = PrometheusConfig(
                bind_address=prometheus_bind_address,
                counters_total_suffix=prometheus_counters_total_suffix or False,
                unit_suffix=prometheus_unit_suffix or False,
                durations_as_seconds=prometheus_durations_as_seconds or False,
            )

    telemetry_config = TelemetryConfig(
        logging=logging,
        metrics=metrics,
        global_tags=global_tags,
        attach_service_name=attach_service_name,
        metric_prefix=metric_prefix,
    )
    try:
        return Runtime(telemetry=telemetry_config)
    except ValueError as err:
        err_msg = str(err)
        if "Address already in use" in err_msg:
            logger.warning("Prometheus exporter port is already in use. Disabling metrics for this process.")
            telemetry_config_no_metrics = TelemetryConfig(
                logging=logging,
                metrics=None,
                global_tags=global_tags,
                attach_service_name=attach_service_name,
                metric_prefix=metric_prefix,
            )
            return Runtime(telemetry=telemetry_config_no_metrics)
        raise
