import logging
from unittest.mock import MagicMock, patch

import pytest

from temporal_boost.temporal.runtime import TemporalRuntimeBuilder


class TestTemporalRuntimeBuilder:
    def test_init_with_defaults(self):
        builder = TemporalRuntimeBuilder()
        assert builder._logging is not None
        assert builder._metrics is None
        assert builder._global_tags == {}
        assert builder._attach_service_name is True

    def test_init_with_logging(self):
        logging_config = MagicMock()
        builder = TemporalRuntimeBuilder(logging=logging_config)
        assert builder._logging == logging_config

    def test_init_with_metrics(self):
        metrics_config = MagicMock()
        builder = TemporalRuntimeBuilder(metrics=metrics_config)
        assert builder._metrics == metrics_config

    def test_init_with_global_tags(self):
        builder = TemporalRuntimeBuilder(global_tags={"tag1": "value1", "tag2": "value2"})
        assert builder._global_tags == {"tag1": "value1", "tag2": "value2"}

    def test_init_with_attach_service_name(self):
        builder = TemporalRuntimeBuilder(attach_service_name=False)
        assert builder._attach_service_name is False

    def test_init_with_metric_prefix(self):
        builder = TemporalRuntimeBuilder(metric_prefix="test_prefix")
        assert builder._metric_prefix == "test_prefix"

    def test_init_with_prometheus_bind_address(self):
        builder = TemporalRuntimeBuilder(prometheus_bind_address="0.0.0.0:9090")
        assert builder._prometheus_bind_address == "0.0.0.0:9090"

    def test_init_with_prometheus_counters_total_suffix(self):
        builder = TemporalRuntimeBuilder(prometheus_counters_total_suffix=True)
        assert builder._prometheus_counters_total_suffix is True

    def test_init_with_prometheus_unit_suffix(self):
        builder = TemporalRuntimeBuilder(prometheus_unit_suffix=True)
        assert builder._prometheus_unit_suffix is True

    def test_init_with_prometheus_durations_as_seconds(self):
        builder = TemporalRuntimeBuilder(prometheus_durations_as_seconds=True)
        assert builder._prometheus_durations_as_seconds is True

    def test_build_without_metrics(self):
        builder = TemporalRuntimeBuilder()
        runtime = builder.build()
        assert runtime is not None

    def test_build_with_prometheus_config(self):
        builder = TemporalRuntimeBuilder(prometheus_bind_address="0.0.0.0:9090")
        runtime = builder.build()
        assert runtime is not None

    def test_build_with_custom_metrics(self):
        from temporalio.runtime import PrometheusConfig

        metrics_config = PrometheusConfig(bind_address="0.0.0.0:9091")
        builder = TemporalRuntimeBuilder(metrics=metrics_config)
        runtime = builder.build()
        assert runtime is not None

    def test_build_with_all_prometheus_options(self):
        builder = TemporalRuntimeBuilder(
            prometheus_bind_address="0.0.0.0:9090",
            prometheus_counters_total_suffix=True,
            prometheus_unit_suffix=True,
            prometheus_durations_as_seconds=True,
        )
        runtime = builder.build()
        assert runtime is not None

    def test_build_with_global_tags(self):
        builder = TemporalRuntimeBuilder(global_tags={"service": "test"})
        runtime = builder.build()
        assert runtime is not None

    def test_build_with_metric_prefix(self):
        builder = TemporalRuntimeBuilder(metric_prefix="test_prefix")
        runtime = builder.build()
        assert runtime is not None

    def test_build_with_address_in_use_error(self, caplog):
        builder = TemporalRuntimeBuilder(prometheus_bind_address="0.0.0.0:9093")

        with patch("temporal_boost.temporal.runtime.Runtime") as mock_runtime_class:
            mock_runtime_instance = MagicMock()
            mock_runtime_class.side_effect = [
                ValueError("Address already in use"),
                mock_runtime_instance,
            ]

            with caplog.at_level(logging.WARNING, logger="temporal_boost.temporal.runtime"):
                runtime = builder.build()

            assert runtime is not None
            assert mock_runtime_class.call_count == 2

    def test_build_with_other_value_error(self):
        builder = TemporalRuntimeBuilder(prometheus_bind_address="0.0.0.0:9094")

        with patch("temporal_boost.temporal.runtime.Runtime") as mock_runtime_class:
            mock_runtime_class.side_effect = ValueError("Other error message")

            with pytest.raises(ValueError, match="Other error message"):
                builder.build()

