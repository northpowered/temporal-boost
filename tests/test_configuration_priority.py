import importlib.util
import json
import os
import subprocess  # noqa: S404
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from temporal_boost import BoostApp
from temporal_boost.temporal import client as client_module, config
from temporal_boost.temporal.client import TemporalClientBuilder
from temporal_boost.workers import temporal as worker_module


@pytest.fixture(params=[False, True], ids=["defaults", "environment"])
def client_config(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    for name in ("TEMPORAL_TARGET_HOST", "TEMPORAL_NAMESPACE"):
        monkeypatch.delenv(name, raising=False)
    if request.param:
        monkeypatch.setenv("TEMPORAL_TARGET_HOST", "env.example:7233")
        monkeypatch.setenv("TEMPORAL_NAMESPACE", "env-namespace")

    # Read real environment values without reloading modules shared with other tests.
    spec = importlib.util.spec_from_file_location("isolated_priority_config", config.__file__)
    assert spec is not None
    assert spec.loader is not None
    isolated = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(isolated)
    expected_host = "env.example:7233" if request.param else "localhost:7233"
    expected_namespace = "env-namespace" if request.param else "default"
    assert expected_host == isolated.TARGET_HOST
    assert expected_namespace == isolated.CLIENT_NAMESPACE
    monkeypatch.setattr(client_module, "config", isolated)
    monkeypatch.setattr(worker_module, "config", isolated)
    return isolated


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("app_options", "worker_calls", "expected_overrides"),
    [
        ({}, [], {}),
        ({"temporal_endpoint": "app.example:7233"}, [], {"target_host": "app.example:7233"}),
        ({"temporal_namespace": "app-namespace"}, [], {"namespace": "app-namespace"}),
        (
            {"temporal_endpoint": "app.example:7233", "temporal_namespace": "app-namespace"},
            [],
            {"target_host": "app.example:7233", "namespace": "app-namespace"},
        ),
        (
            {"temporal_endpoint": "app.example:7233", "temporal_namespace": "app-namespace"},
            [{"target_host": "worker.example:7233"}],
            {"target_host": "worker.example:7233", "namespace": "app-namespace"},
        ),
        (
            {"temporal_endpoint": "app.example:7233", "temporal_namespace": "app-namespace"},
            [{"namespace": "worker-namespace"}],
            {"target_host": "app.example:7233", "namespace": "worker-namespace"},
        ),
        (
            {"temporal_endpoint": "app.example:7233", "temporal_namespace": "app-namespace"},
            [
                {"target_host": "worker.example:7233", "namespace": "worker-namespace"},
                {"target_host": "last.example:7233"},
                {"target_host": None, "namespace": None},
            ],
            {"target_host": "last.example:7233", "namespace": "worker-namespace"},
        ),
        ({"temporal_endpoint": "", "temporal_namespace": ""}, [], {"target_host": "", "namespace": ""}),
        ({}, [{"target_host": "", "namespace": ""}], {"target_host": "", "namespace": ""}),
    ],
)
async def test_worker_app_environment_connection_priority(
    client_config: ModuleType,
    app_options: dict[str, str],
    worker_calls: list[dict[str, str | None]],
    expected_overrides: dict[str, str],
) -> None:
    app = BoostApp(logger_config=None, **app_options)
    worker = app.add_worker("consumer", "queue", activities=[MagicMock()])
    for options in worker_calls:
        worker.configure_temporal_client(**options)

    with (
        patch("temporal_boost.temporal.runtime.TemporalRuntimeBuilder.build", return_value=MagicMock()),
        patch("temporal_boost.temporal.client.Client.connect", new_callable=AsyncMock) as connect,
        patch.object(worker._worker_builder, "build"),
    ):
        await worker._build_worker()

    expected = {"target_host": client_config.TARGET_HOST, "namespace": client_config.CLIENT_NAMESPACE}
    expected.update(expected_overrides)
    connect.assert_awaited_once()
    assert {key: connect.call_args.kwargs[key] for key in expected} == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("options", "expected_overrides"),
    [
        ({}, {}),
        ({"target_host": None, "namespace": None}, {}),
        ({"target_host": "", "namespace": ""}, {}),
        (
            {"target_host": "client.example:7233", "namespace": "client-namespace"},
            {"target_host": "client.example:7233", "namespace": "client-namespace"},
        ),
    ],
)
async def test_client_constructor_connection_priority(
    client_config: ModuleType, options: dict[str, str | None], expected_overrides: dict[str, str]
) -> None:
    builder = TemporalClientBuilder(**options)
    builder.set_runtime(MagicMock())
    with patch("temporal_boost.temporal.client.Client.connect", new_callable=AsyncMock) as connect:
        await builder.build()

    expected = {"target_host": client_config.TARGET_HOST, "namespace": client_config.CLIENT_NAMESPACE}
    expected.update(expected_overrides)
    assert {key: connect.call_args.kwargs[key] for key in expected} == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(("tls", "expected"), [(None, True), (False, False), (True, True)])
async def test_client_tls_false_overrides_imported_true(
    client_config: ModuleType, monkeypatch: pytest.MonkeyPatch, tls: bool | None, expected: bool
) -> None:
    monkeypatch.setattr(client_config, "CLIENT_TLS", True)
    builder = TemporalClientBuilder(tls=tls)
    builder.set_runtime(MagicMock())
    with patch("temporal_boost.temporal.client.Client.connect", new_callable=AsyncMock) as connect:
        await builder.build()
    assert connect.call_args.kwargs["tls"] is expected


@pytest.mark.asyncio
async def test_worker_tls_none_keeps_explicit_false(client_config: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_config, "CLIENT_TLS", True)
    worker = BoostApp(logger_config=None).add_worker("worker", "queue", activities=[MagicMock()])
    worker.configure_temporal_client(tls=False)
    worker.configure_temporal_client(tls=None)
    assert worker._client_builder is not None
    worker._client_builder.set_runtime(MagicMock())
    with patch("temporal_boost.temporal.client.Client.connect", new_callable=AsyncMock) as connect:
        await worker._client_builder.build()
    assert connect.call_args.kwargs["tls"] is False


def run_configuration_probe(tmp_path: Path, script: str, **environment: str) -> dict[str, Any]:
    probe_env = {key: value for key, value in os.environ.items() if not key.startswith("TEMPORAL_")}
    probe_env.update(environment)
    project_root = Path(__file__).resolve().parent.parent
    probe_env["PYTHONPATH"] = str(project_root)
    if probe_env.get("COV_CORE_CONFIG") == os.pathsep:
        # pytest-cov 5 auto-detection cannot find the project's branch settings from tmp_path.
        probe_env["COV_CORE_CONFIG"] = str(project_root / "pyproject.toml")
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=probe_env,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_package_does_not_load_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "TEMPORAL_TARGET_HOST=dotenv.example:7233\nTEMPORAL_NAMESPACE=dotenv-namespace\n", encoding="utf-8"
    )
    values = run_configuration_probe(
        tmp_path,
        """
import json
from temporal_boost.temporal import config
print(json.dumps({"host": config.TARGET_HOST, "namespace": config.CLIENT_NAMESPACE}))
""",
    )
    assert values == {"host": "localhost:7233", "namespace": "default"}


def test_environment_changes_after_import_do_not_reconfigure_new_builders(tmp_path: Path) -> None:
    values = run_configuration_probe(
        tmp_path,
        """
import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
from temporal_boost.temporal.client import TemporalClientBuilder
from temporal_boost.temporal.worker import TemporalWorkerBuilder

os.environ.update(TEMPORAL_TARGET_HOST="later.example:7233", TEMPORAL_NAMESPACE="later-namespace",
                  TEMPORAL_MAX_CONCURRENT_ACTIVITIES="23", TEMPORAL_NONSTICKY_TO_STICKY_RATIO="0.5")
client = TemporalClientBuilder()
client.set_runtime(MagicMock())
with patch("temporal_boost.temporal.client.Client.connect", new_callable=AsyncMock) as connect:
    asyncio.run(client.build())
worker = TemporalWorkerBuilder("queue")
worker.set_client(MagicMock())
with patch("temporal_boost.temporal.worker.Worker") as sdk_worker:
    worker.build()
print(json.dumps({"host": connect.call_args.kwargs["target_host"],
                  "namespace": connect.call_args.kwargs["namespace"],
                  "activities": sdk_worker.call_args.kwargs["max_concurrent_activities"],
                  "ratio": sdk_worker.call_args.kwargs["nonsticky_to_sticky_poll_ratio"]}))
""",
        TEMPORAL_TARGET_HOST="first.example:7233",
        TEMPORAL_NAMESPACE="first-namespace",
        TEMPORAL_MAX_CONCURRENT_ACTIVITIES="17",
        TEMPORAL_NONSTICKY_TO_STICKY_RATIO="0.0",
    )
    assert values == {"host": "first.example:7233", "namespace": "first-namespace", "activities": 17, "ratio": 0.0}


def test_runtime_defaults_are_captured_at_import_and_explicit_none_disables_prometheus(tmp_path: Path) -> None:
    values = run_configuration_probe(
        tmp_path,
        """
import json
import os
from unittest.mock import MagicMock, patch
from temporal_boost import BoostApp
from temporal_boost.temporal import config
from temporal_boost.temporal.runtime import TemporalRuntimeBuilder

os.environ["TEMPORAL_PROMETHEUS_BIND_ADDRESS"] = "127.0.0.1:9201"
config.PROMETHEUS_BIND_ADDRESS = "127.0.0.1:9202"
config.PROMETHEUS_COUNTERS_TOTAL_SUFFIX = False
config.PROMETHEUS_UNIT_SUFFIX = False
config.PROMETHEUS_DURATIONS_AS_SECONDS = False

with patch("temporal_boost.temporal.runtime.Runtime") as runtime:
    TemporalRuntimeBuilder().build()
    standalone = runtime.call_args.kwargs["telemetry"].metrics
    worker = BoostApp(logger_config=None).add_worker("worker", "queue", activities=[MagicMock()])
    worker.configure_temporal_runtime()
    worker.temporal_client_runtime
    configured = runtime.call_args.kwargs["telemetry"].metrics
    TemporalRuntimeBuilder(prometheus_bind_address=None).build()
    disabled = runtime.call_args.kwargs["telemetry"].metrics
    worker = BoostApp(logger_config=None).add_worker("worker", "queue", activities=[MagicMock()])
    worker.configure_temporal_runtime(prometheus_bind_address=None)
    worker.temporal_client_runtime
    worker_disabled = runtime.call_args.kwargs["telemetry"].metrics
    explicit_flags = []
    for flag in (None, False):
        TemporalRuntimeBuilder(prometheus_bind_address="127.0.0.1:9203",
                               prometheus_counters_total_suffix=flag,
                               prometheus_unit_suffix=flag,
                               prometheus_durations_as_seconds=flag).build()
        explicit_flags.append(vars(runtime.call_args.kwargs["telemetry"].metrics))
print(json.dumps({"standalone": vars(standalone), "configured": vars(configured),
                  "disabled": disabled, "worker_disabled": worker_disabled, "explicit_flags": explicit_flags}))
""",
        TEMPORAL_PROMETHEUS_BIND_ADDRESS="127.0.0.1:9200",
        TEMPORAL_PROMETHEUS_COUNTERS_TOTAL_SUFFIX="true",
        TEMPORAL_PROMETHEUS_UNIT_SUFFIX="true",
        TEMPORAL_PROMETHEUS_DURATIONS_AS_SECONDS="true",
    )
    for source in ("standalone", "configured"):
        assert values[source]["bind_address"] == "127.0.0.1:9200"
        assert values[source]["counters_total_suffix"] is True
        assert values[source]["unit_suffix"] is True
        assert values[source]["durations_as_seconds"] is True
    assert values["disabled"] is None
    assert values["worker_disabled"] is None
    for explicit in values["explicit_flags"]:
        assert explicit["counters_total_suffix"] is False
        assert explicit["unit_suffix"] is False
        assert explicit["durations_as_seconds"] is False
