from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess  # noqa: S404
import sys
import time
import uuid
from contextlib import ExitStack, contextmanager
from datetime import timedelta
from http.client import HTTPConnection
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.runtime import LoggingConfig, MetricBuffer, OpenTelemetryConfig, PrometheusConfig, Runtime
from temporalio.testing import WorkflowEnvironment

from temporal_boost.temporal.runtime import TemporalRuntimeBuilder
from temporal_boost.workers.temporal import TemporalBoostWorker
from tests.metrics_exporter_app import MetricsProbe, metrics_probe


if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


@pytest.mark.parametrize("address", ["127.0.0.1:9090", "localhost:9090", "[::1]:9090"])
@pytest.mark.parametrize("source", ["bind-address", "metrics-only", "metrics-override"])
def test_prometheus_failure_preserves_cause_and_does_not_retry_without_metrics(
    address: str, source: str, caplog: pytest.LogCaptureFixture
) -> None:
    logging_config = LoggingConfig(filter="ERROR")
    bind_address = {"bind-address": address, "metrics-only": None, "metrics-override": "ignored:9999"}[source]
    builder = TemporalRuntimeBuilder(
        logging=logging_config,
        metrics=None if source == "bind-address" else PrometheusConfig(address),
        prometheus_bind_address=bind_address,
        global_tags={"worker": "second"},
        attach_service_name=False,
        metric_prefix="custom_",
    )
    failure = ValueError("Address already in use")
    with patch("temporal_boost.temporal.runtime.Runtime", side_effect=failure) as create:
        with pytest.raises(ValueError, match="Address already in use") as raised:
            builder.build()
    assert raised.value is failure
    create.assert_called_once()
    telemetry = create.call_args.kwargs["telemetry"]
    assert telemetry.logging is logging_config
    assert telemetry.metrics.bind_address == address
    assert telemetry.global_tags == {"worker": "second"}
    assert telemetry.attach_service_name is False
    assert telemetry.metric_prefix == "custom_"
    assert address in caplog.text
    assert "ignored:9999" not in caplog.text
    assert "distinct endpoint" in caplog.text


@pytest.mark.parametrize("metrics", [None, OpenTelemetryConfig("http://collector:4317"), MetricBuffer(100)])
def test_non_prometheus_backend_does_not_claim_to_bind_prometheus(
    metrics: OpenTelemetryConfig | MetricBuffer | None, caplog: pytest.LogCaptureFixture
) -> None:
    builder = TemporalRuntimeBuilder(
        metrics=metrics, prometheus_bind_address=None if metrics is None else "ignored:9090"
    )
    with caplog.at_level(logging.INFO), patch("temporal_boost.temporal.runtime.Runtime") as create:
        runtime = builder.build()
    assert runtime is create.return_value
    assert create.call_args.kwargs["telemetry"].metrics is metrics
    assert "bound" not in caplog.text


@pytest.mark.parametrize("metrics", [OpenTelemetryConfig("http://collector:4317"), MetricBuffer(100)])
def test_other_metrics_backend_failure_does_not_claim_prometheus_conflict(
    metrics: OpenTelemetryConfig | MetricBuffer, caplog: pytest.LogCaptureFixture
) -> None:
    failure = ValueError("Address already in use")
    builder = TemporalRuntimeBuilder(metrics=metrics, prometheus_bind_address="ignored:9090")
    with caplog.at_level(logging.INFO), patch("temporal_boost.temporal.runtime.Runtime", side_effect=failure) as create:
        with pytest.raises(ValueError, match="Address already in use") as raised:
            builder.build()
    assert raised.value is failure
    create.assert_called_once()
    assert create.call_args.kwargs["telemetry"].metrics is metrics
    assert "Prometheus" not in caplog.text
    assert "ignored:9090" not in caplog.text


@pytest.mark.parametrize("address", ["127.0.0.1:9090", "[::1]:9090"])
def test_prometheus_success_logs_effective_endpoint_only(address: str, caplog: pytest.LogCaptureFixture) -> None:
    metrics = PrometheusConfig(address)
    builder = TemporalRuntimeBuilder(metrics=metrics, prometheus_bind_address="ignored:9999")
    with caplog.at_level(logging.INFO), patch("temporal_boost.temporal.runtime.Runtime") as create:
        runtime = builder.build()
    create.assert_called_once()
    assert runtime is create.return_value
    assert create.call_args.kwargs["telemetry"].metrics is metrics
    assert f"Prometheus exporter bound to {address}" in caplog.text
    assert "ignored:9999" not in caplog.text


def test_unrelated_error_with_prometheus_preserves_original_diagnostic(caplog: pytest.LogCaptureFixture) -> None:
    failure = ValueError("invalid logging filter")
    with patch("temporal_boost.temporal.runtime.Runtime", side_effect=failure) as create:
        with pytest.raises(ValueError, match="invalid logging filter") as raised:
            TemporalRuntimeBuilder(metrics=PrometheusConfig("[::1]:9090"), prometheus_bind_address=None).build()
    assert raised.value is failure
    create.assert_called_once()
    assert "invalid logging filter" in caplog.text
    assert "Address already in use" not in caplog.text
    assert "exporter bound" not in caplog.text


def test_unrelated_runtime_error_is_not_reclassified_as_port_conflict() -> None:
    failure = ValueError("invalid logging filter")
    with patch("temporal_boost.temporal.runtime.Runtime", side_effect=failure) as create:
        with pytest.raises(ValueError, match="invalid logging filter") as raised:
            TemporalRuntimeBuilder(prometheus_bind_address=None).build()
    assert raised.value is failure
    create.assert_called_once()


@pytest.mark.asyncio
async def test_worker_runtimes_are_lazy_independent_and_forwarded_to_their_clients() -> None:
    workers = [
        TemporalBoostWorker(f"worker-{index}", f"queue-{index}", activities=[metrics_probe]) for index in range(2)
    ]
    runtimes = [MagicMock(spec_set=Runtime), MagicMock(spec_set=Runtime)]
    with (
        patch("temporal_boost.temporal.runtime.Runtime", side_effect=runtimes) as create,
        patch("temporal_boost.temporal.client.Client.connect", new_callable=AsyncMock) as connect,
        patch("temporal_boost.temporal.worker.TemporalWorkerBuilder.build"),
    ):
        for index, worker in enumerate(workers):
            worker.configure_temporal_runtime(prometheus_bind_address=f"127.0.0.1:{9100 + index}")
        create.assert_not_called()
        for index, worker in enumerate(workers):
            await worker._build_worker()
            assert worker.temporal_client_runtime is runtimes[index]
            assert connect.call_args.kwargs["runtime"] is runtimes[index]
        assert create.call_count == 2
        workers[0]._release_resources()
        assert workers[0]._runtime is None
        assert workers[1].temporal_client_runtime is runtimes[1]
        assert create.call_count == 2


def scrape(port: int) -> str:
    connection = HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", "/metrics")
        response = connection.getresponse()
        assert response.status == 200
        return response.read().decode()
    finally:
        connection.close()


def metric_samples(metrics: str, name: str = "boost_metrics_probe_total") -> list[tuple[dict[str, str], float]]:
    return [
        (dict(re.findall(r'(\w+)="([^"]*)"', labels)), float(value))
        for labels, value in re.findall(rf"^{re.escape(name)}\{{(.*?)\}} (\S+)$", metrics, re.MULTILINE)
    ]


def exporter_command(mode: str, ports: list[int], ready: Path, target: str = "localhost:7233") -> list[str]:
    return [
        sys.executable,
        "-u",
        "-m",
        "tests.metrics_exporter_app",
        mode,
        ",".join(map(str, ports)),
        str(ready),
        target,
    ]


@contextmanager
def exporters(
    directory: Path, ports: list[int], *, mode: str = "meter", target: str = "localhost:7233"
) -> Iterator[dict[str, object]]:
    ready = directory / f"ready-{ports[0]}"
    process = subprocess.Popen(  # noqa: S603
        exporter_command(mode, ports, ready, target),
        cwd=Path(__file__).resolve().parents[1],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists():
            assert time.monotonic() < deadline, "exporters did not become ready"
            if process.poll() is not None:
                pytest.fail(f"exporters failed: {process.communicate(timeout=1)}")
            time.sleep(0.01)
        yield json.loads(ready.read_text())
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
            pytest.fail("exporter process did not stop")


@pytest.mark.parametrize("process_count", [1, 2])
def test_real_sdk_exporters_include_both_worker_runtimes_in_every_process(
    tmp_path: Path, unused_tcp_port_factory: Callable[[], int], process_count: int
) -> None:
    with ExitStack() as stack:
        total = 0.0
        for _index in range(process_count):
            ports = [unused_tcp_port_factory(), unused_tcp_port_factory()]
            info = stack.enter_context(exporters(tmp_path, ports))
            for worker_index, port in enumerate(ports):
                metrics = scrape(port)
                samples = metric_samples(metrics)
                assert len(samples) == 1
                _labels, value = samples[0]
                metadata, _value = metric_samples(metrics, "target_info")[0]
                assert metadata["boost_worker"] == f"worker-{worker_index}"
                assert metadata["process_id"] == str(info["pid"])
                assert value == worker_index + 1
                total += value
        assert total == 3 * process_count


def test_real_conflicting_runtime_cannot_continue_with_missing_metrics(
    tmp_path: Path, unused_tcp_port_factory: Callable[[], int]
) -> None:
    ports = [unused_tcp_port_factory(), unused_tcp_port_factory()]
    with exporters(tmp_path, ports):
        result = subprocess.run(  # noqa: S603
            exporter_command("meter", ports, tmp_path / "conflicting-ready"),
            cwd=Path(__file__).resolve().parents[1],
            input="",
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert f"127.0.0.1:{ports[0]}" in result.stderr
        assert "distinct endpoint" in result.stderr
        assert not (tmp_path / "conflicting-ready").exists()
        assert all(metric_samples(scrape(port)) for port in ports)


def test_real_duplicate_worker_endpoint_in_one_process_is_fatal(tmp_path: Path, unused_tcp_port: int) -> None:
    ready = tmp_path / "duplicate-ready"
    result = subprocess.run(  # noqa: S603
        exporter_command("meter", [unused_tcp_port, unused_tcp_port], ready),
        cwd=Path(__file__).resolve().parents[1],
        input="",
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "distinct endpoint" in result.stderr
    assert not ready.exists()


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("TEMPORAL_BOOST_INTEGRATION") != "1", reason="requires opt-in real Temporal dev server")
async def test_real_activities_export_metrics_from_two_workers_in_each_of_two_processes(
    tmp_path: Path, unused_tcp_port_factory: Callable[[], int]
) -> None:
    async with await WorkflowEnvironment.start_local(
        ip="127.0.0.1", dev_server_existing_path=os.getenv("TEMPORAL_CLI_PATH"), dev_server_log_level="error"
    ) as env:
        with ExitStack() as stack:
            endpoints = []
            executions = []
            for _index in range(2):
                ports = [unused_tcp_port_factory(), unused_tcp_port_factory()]
                info = stack.enter_context(
                    exporters(tmp_path, ports, mode="workers", target=env.client.service_client.config.target_host)
                )
                for port, queue in zip(ports, info["queues"], strict=True):
                    endpoints.append((port, queue, str(info["pid"])))
                    executions.append(
                        env.client.execute_workflow(
                            MetricsProbe.run,
                            id=str(uuid.uuid4()),
                            task_queue=queue,
                            execution_timeout=timedelta(seconds=20),
                        )
                    )
            results = await asyncio.gather(*executions)
            assert set(results) == {queue for _port, queue, _pid in endpoints}
            total = 0.0
            for port, queue, pid in endpoints:
                metrics = scrape(port)
                samples = metric_samples(metrics)
                assert len(samples) == 1
                labels, value = samples[0]
                metadata, _value = metric_samples(metrics, "target_info")[0]
                assert metadata["process_id"] == pid
                assert labels["task_queue"] == queue
                assert value == 1
                assert "temporal_activity_execution_latency_count" in metrics
                assert f'task_queue="{queue}"' in metrics
                total += value
            assert total == 4
