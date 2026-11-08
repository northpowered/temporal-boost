import logging
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from temporalio.runtime import PrometheusConfig

from temporal_boost.temporal.runtime import TemporalRuntimeBuilder


class TestTemporalRuntimeBuilder:
    @pytest.fixture(autouse=True)
    def mock_runtime(self) -> Iterator[MagicMock]:
        with patch("temporal_boost.temporal.runtime.Runtime") as runtime:
            yield runtime

    def test_init_with_defaults(self) -> None:
        builder = TemporalRuntimeBuilder()
        assert builder._logging is not None
        assert builder._metrics is None
        assert builder._global_tags == {}
        assert builder._attach_service_name is True

    def test_init_with_logging(self) -> None:
        logging_config = MagicMock()
        builder = TemporalRuntimeBuilder(logging=logging_config)
        assert builder._logging == logging_config

    def test_init_with_metrics(self) -> None:
        metrics_config = MagicMock()
        builder = TemporalRuntimeBuilder(metrics=metrics_config)
        assert builder._metrics == metrics_config

    def test_init_with_global_tags(self) -> None:
        builder = TemporalRuntimeBuilder(global_tags={"tag1": "value1", "tag2": "value2"})
        assert builder._global_tags == {"tag1": "value1", "tag2": "value2"}

    def test_init_with_attach_service_name(self) -> None:
        builder = TemporalRuntimeBuilder(attach_service_name=False)
        assert builder._attach_service_name is False

    def test_init_with_metric_prefix(self) -> None:
        builder = TemporalRuntimeBuilder(metric_prefix="test_prefix")
        assert builder._metric_prefix == "test_prefix"

    def test_init_with_prometheus_bind_address(self) -> None:
        builder = TemporalRuntimeBuilder(prometheus_bind_address="0.0.0.0:9090")
        assert builder._prometheus_bind_address == "0.0.0.0:9090"

    def test_init_with_prometheus_counters_total_suffix(self) -> None:
        builder = TemporalRuntimeBuilder(prometheus_counters_total_suffix=True)
        assert builder._prometheus_counters_total_suffix is True

    def test_init_with_prometheus_unit_suffix(self) -> None:
        builder = TemporalRuntimeBuilder(prometheus_unit_suffix=True)
        assert builder._prometheus_unit_suffix is True

    def test_init_with_prometheus_durations_as_seconds(self) -> None:
        builder = TemporalRuntimeBuilder(prometheus_durations_as_seconds=True)
        assert builder._prometheus_durations_as_seconds is True

    def test_build_without_metrics(self) -> None:
        builder = TemporalRuntimeBuilder()
        runtime = builder.build()
        assert runtime is not None

    def test_build_with_prometheus_config(self) -> None:
        builder = TemporalRuntimeBuilder(prometheus_bind_address="0.0.0.0:9090")
        runtime = builder.build()
        assert runtime is not None

    def test_build_with_custom_metrics(self) -> None:
        metrics_config = PrometheusConfig(bind_address="0.0.0.0:9091")
        builder = TemporalRuntimeBuilder(metrics=metrics_config)
        runtime = builder.build()
        assert runtime is not None

    def test_build_with_all_prometheus_options(self) -> None:
        builder = TemporalRuntimeBuilder(
            prometheus_bind_address="0.0.0.0:9090",
            prometheus_counters_total_suffix=True,
            prometheus_unit_suffix=True,
            prometheus_durations_as_seconds=True,
        )
        runtime = builder.build()
        assert runtime is not None

    def test_build_with_global_tags(self) -> None:
        builder = TemporalRuntimeBuilder(global_tags={"service": "test"})
        runtime = builder.build()
        assert runtime is not None

    def test_build_with_metric_prefix(self) -> None:
        builder = TemporalRuntimeBuilder(metric_prefix="test_prefix")
        runtime = builder.build()
        assert runtime is not None

    def test_build_with_address_in_use_error(self, caplog: pytest.LogCaptureFixture) -> None:
        builder = TemporalRuntimeBuilder(prometheus_bind_address="0.0.0.0:9093")

        with patch("temporal_boost.temporal.runtime.Runtime") as mock_runtime_class:
            failure = ValueError("Address already in use")
            mock_runtime_class.side_effect = failure

            with caplog.at_level(logging.ERROR, logger="temporal_boost.temporal.runtime"):
                with pytest.raises(ValueError, match="Address already in use") as raised:
                    builder.build()

            assert raised.value is failure
            assert mock_runtime_class.call_count == 1
            assert "0.0.0.0:9093" in caplog.text

    def test_build_with_other_value_error(self) -> None:
        builder = TemporalRuntimeBuilder(prometheus_bind_address="0.0.0.0:9094")

        with patch("temporal_boost.temporal.runtime.Runtime") as mock_runtime_class:
            mock_runtime_class.side_effect = ValueError("Other error message")

            with pytest.raises(ValueError, match="Other error message"):
                builder.build()
