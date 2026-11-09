import asyncio
import json
import logging
import os
import sys
import tempfile
import threading
import traceback
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.converter import DataConverter
from typer.testing import CliRunner

from temporal_boost import BaseBoostWorker
from temporal_boost.boost_app import BoostApp
from temporal_boost.temporal import config
from temporal_boost.workers.temporal import TemporalBoostWorker


class RegistrationWorker(BaseBoostWorker):
    def __init__(self, name: str = "internal", app: BoostApp | None = None) -> None:
        self.name = name
        self.app = app
        self.calls: list[tuple[str, str, str]] = []
        self.shutdown_calls = 0

    def run(self, label: str = "default") -> None:
        self.calls.append((self.name, threading.current_thread().name, label))
        if self.app is not None:
            self.app.stop()
        asyncio.run(self.shutdown())

    def request_stop(self) -> bool:
        return True

    async def shutdown(self) -> None:
        self.shutdown_calls += 1


@pytest.mark.parametrize("command", [["run", "alias", "--label", "selected"], ["run", "all"]])
def test_custom_registration_uses_alias_in_cli_registry_and_threads(command: list[str]) -> None:
    app = BoostApp(logger_config=None)
    worker = RegistrationWorker(app=app)
    app.add_async_runtime("alias", worker)

    result = CliRunner().invoke(app._root_typer, command)

    assert result.exit_code == 0, result.exception
    assert app.get_registered_workers() == [worker]
    assert worker.name == "alias"
    expected_thread = "worker-alias" if command[-1] == "all" else threading.current_thread().name
    expected_label = "default" if command[-1] == "all" else "selected"
    assert worker.calls == [("alias", expected_thread, expected_label)]
    assert worker.shutdown_calls == 1
    missing = CliRunner().invoke(app._root_typer, ["run", "internal"])
    assert missing.exit_code == 2
    assert "No such command" in missing.output


def register_worker_kind(app: BoostApp, kind: str, name: str) -> BaseBoostWorker:
    if kind == "temporal":
        return app.add_worker(name, "queue", activities=[MagicMock()])
    if kind == "asgi":
        worker_class = MagicMock(return_value=RegistrationWorker())
        with patch("temporal_boost.boost_app.get_asgi_worker_class", return_value=worker_class):
            app.add_asgi_worker(name, None, "127.0.0.1", 8000)
        return app.get_registered_workers()[-1]
    if kind == "faststream":
        with patch("temporal_boost.boost_app.FastStreamBoostWorker", return_value=RegistrationWorker()):
            return app.add_faststream_worker(name, None)
    worker = RegistrationWorker()
    app.add_async_runtime(name, worker)
    return worker


WORKER_KINDS = ["temporal", "asgi", "faststream", "custom"]


@pytest.mark.parametrize("first_kind", WORKER_KINDS)
@pytest.mark.parametrize("second_kind", WORKER_KINDS)
def test_worker_names_are_unique_across_all_registration_methods(first_kind: str, second_kind: str) -> None:
    app = BoostApp(logger_config=None)
    first = register_worker_kind(app, first_kind, "alias")
    with pytest.raises(RuntimeError, match="already registered"):
        register_worker_kind(app, second_kind, "alias")
    assert app.get_registered_workers() == [first]
    assert len(app._run_typer.registered_commands) == 2  # run all and the original command


@pytest.mark.parametrize("kind", WORKER_KINDS)
@pytest.mark.parametrize("name", ["run", "cron", "exec", "all"])
def test_all_worker_registration_methods_reject_reserved_names(kind: str, name: str) -> None:
    app = BoostApp(logger_config=None)
    with pytest.raises(RuntimeError, match="reserved"):
        register_worker_kind(app, kind, name)
    assert app.get_registered_workers() == []
    assert len(app._run_typer.registered_commands) == 1


@pytest.mark.parametrize("kind", WORKER_KINDS)
@pytest.mark.parametrize("alias", ["original", "second"])
def test_same_worker_object_cannot_be_registered_twice(kind: str, alias: str) -> None:
    app = BoostApp(logger_config=None)
    worker = register_worker_kind(app, kind, "original")
    with pytest.raises(RuntimeError, match="already registered"):
        app.add_async_runtime(alias, worker)
    assert worker.name == "original"
    assert app.get_registered_workers() == [worker]
    assert len(app._run_typer.registered_commands) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("preconfigured", [False, True])
async def test_precreated_temporal_registration_preserves_configuration(
    monkeypatch: pytest.MonkeyPatch, preconfigured: bool
) -> None:
    monkeypatch.setattr(config, "TARGET_HOST", "env.example:7233")
    monkeypatch.setattr(config, "CLIENT_NAMESPACE", "env-namespace")
    monkeypatch.setattr(config, "USE_PYDANTIC_DATA_CONVERTER", False)
    app = BoostApp(
        temporal_endpoint="app.example:7233", temporal_namespace="app-namespace", use_pydantic=True, logger_config=None
    )
    worker = TemporalBoostWorker("internal", "queue", activities=[MagicMock()])
    if preconfigured:
        worker.configure_temporal_client(target_host="worker.example:7233", namespace="worker-namespace")
    original_builder = worker._client_builder
    original_cron_id = worker.cron_workflow_id
    app.add_async_runtime("alias", worker)
    assert worker._client_builder is original_builder
    assert worker.cron_workflow_id == original_cron_id
    assert worker.name == "alias"

    with (
        patch("temporal_boost.temporal.runtime.TemporalRuntimeBuilder.build", return_value=MagicMock()),
        patch("temporalio.client.Client.connect", new_callable=AsyncMock) as connect,
        patch.object(worker._worker_builder, "build"),
    ):
        await worker._build_worker()

    expected_host = "worker.example:7233" if preconfigured else "env.example:7233"
    expected_namespace = "worker-namespace" if preconfigured else "env-namespace"
    assert connect.call_args.kwargs["target_host"] == expected_host
    assert connect.call_args.kwargs["namespace"] == expected_namespace
    assert "data_converter" not in connect.call_args.kwargs
    assert app._cron_typer.registered_commands == []


@pytest.mark.parametrize(
    ("schedule", "with_runner"),
    [("0 * * * *", False), (None, True), ("", True), (" ", True), ("", False), ("\t\n", False)],
)
def test_invalid_cron_registration_has_no_partial_app_or_connection_side_effects(
    schedule: str | None, with_runner: bool
) -> None:
    app = BoostApp(logger_config=None)

    async def runner() -> None:
        pass

    with patch.object(TemporalBoostWorker, "configure_temporal_client") as configure:
        with pytest.raises(ValueError, match="cron_schedule.*cron_runner|cron_schedule.*non-empty"):
            app.add_worker(
                "invalid_cron",
                "queue",
                activities=[MagicMock()],
                cron_schedule=schedule,
                cron_runner=runner if with_runner else None,
            )

    configure.assert_not_called()
    assert app.get_registered_workers() == []
    result = CliRunner().invoke(app._root_typer, ["run", "invalid_cron"])
    assert result.exit_code == 2
    assert "No such command" in result.output


def test_consumer_registration_has_no_cron_cli_command() -> None:
    app = BoostApp(logger_config=None)
    worker = app.add_worker("consumer", "queue", activities=[MagicMock()])

    result = CliRunner().invoke(app._root_typer, ["cron", "consumer"])

    assert result.exit_code == 2
    assert app.get_registered_workers() == [worker]


@pytest.mark.parametrize("command", [["run", "scheduled"], ["run", "all"], ["cron", "scheduled"]])
def test_cli_cron_registration_is_explicit_and_consumers_never_start_workflows(command: list[str]) -> None:
    app = BoostApp(logger_config=None, shutdown_timeout=2)

    async def runner() -> None:
        pass

    worker = app.add_worker("scheduled", "queue", activities=[runner], cron_schedule="0 * * * *", cron_runner=runner)
    client = MagicMock(start_workflow=AsyncMock())
    sdk = MagicMock(run=AsyncMock(), shutdown=AsyncMock())
    finished: asyncio.Event | None = None

    async def build() -> None:
        nonlocal finished
        finished = asyncio.Event()
        worker._client = client
        worker._worker = sdk

    async def serve() -> None:
        assert finished is not None
        if command == ["run", "all"]:
            app.stop()
        elif command[0] == "run":
            worker.request_stop()
        await finished.wait()

    async def shutdown() -> None:
        assert finished is not None
        finished.set()

    def registered(*_args: object, **_kwargs: object) -> MagicMock:
        worker.request_stop()
        return MagicMock(id=worker.cron_workflow_id, result_run_id="registered-run")

    sdk.run.side_effect = serve
    sdk.shutdown.side_effect = shutdown
    client.start_workflow.side_effect = registered

    with patch.object(worker, "_build_worker", side_effect=build) as build_worker:
        result = CliRunner().invoke(app._root_typer, command)

    assert result.exit_code == 0, result.exception
    assert result.exception is None
    build_worker.assert_awaited_once()
    sdk.run.assert_awaited_once()
    sdk.shutdown.assert_awaited_once()
    assert worker.state == "stopped"
    if command[0] == "cron":
        client.start_workflow.assert_awaited_once()
        assert client.start_workflow.call_args.args == (runner,)
        assert client.start_workflow.call_args.kwargs["cron_schedule"] == "0 * * * *"
    else:
        client.start_workflow.assert_not_awaited()


class TestBoostApp:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("env_enabled", [False, True])
    @pytest.mark.parametrize("use_pydantic", [None, False, True])
    async def test_registered_worker_pydantic_override_matrix(
        self, monkeypatch: pytest.MonkeyPatch, env_enabled: bool, use_pydantic: bool | None
    ) -> None:
        monkeypatch.setattr(config, "USE_PYDANTIC_DATA_CONVERTER", env_enabled)
        app = BoostApp(use_pydantic=use_pydantic, logger_config=None)
        worker = app.add_worker("test_worker", "test_queue", activities=[MagicMock()])

        with (
            patch("temporalio.client.Client.connect", new_callable=AsyncMock) as connect,
            patch.object(worker._worker_builder, "build"),
        ):
            await worker._build_worker()

        enabled = env_enabled if use_pydantic is None else use_pydantic
        if enabled:
            assert connect.call_args.kwargs["data_converter"] is pydantic_data_converter
        else:
            assert "data_converter" not in connect.call_args.kwargs

    @pytest.mark.asyncio
    async def test_worker_converter_overrides_app_pydantic(self) -> None:
        app = BoostApp(use_pydantic=True, logger_config=None)
        worker = app.add_worker("test_worker", "test_queue", activities=[MagicMock()])
        converter = DataConverter()
        worker.configure_temporal_client(data_converter=converter)

        with (
            patch("temporalio.client.Client.connect", new_callable=AsyncMock) as connect,
            patch.object(worker._worker_builder, "build"),
        ):
            await worker._build_worker()

        assert connect.call_args.kwargs["data_converter"] is converter

    def test_init_with_defaults(self):
        app = BoostApp()
        assert app._name == "temporal_generic_service"
        assert app._global_temporal_endpoint is None
        assert app._global_temporal_namespace is None
        assert app._global_use_pydantic is None
        assert app._debug_mode is False
        assert app._registered_workers == []

    def test_init_with_custom_name(self):
        app = BoostApp(name="test_app")
        assert app._name == "test_app"

    def test_init_with_temporal_endpoint(self):
        app = BoostApp(temporal_endpoint="localhost:7233")
        assert app._global_temporal_endpoint == "localhost:7233"

    def test_init_with_temporal_namespace(self):
        app = BoostApp(temporal_namespace="test_namespace")
        assert app._global_temporal_namespace == "test_namespace"

    def test_init_with_debug_mode(self):
        app = BoostApp(debug_mode=True)
        assert app._debug_mode is True

    def test_init_with_use_pydantic(self):
        app = BoostApp(use_pydantic=True)
        assert app._global_use_pydantic is True

    def test_init_with_logger_config_dict(self):
        log_config = {"version": 1, "disable_existing_loggers": False}
        app = BoostApp(logger_config=log_config)
        assert app._logger_config == log_config

    def test_init_with_logger_config_path_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            log_config = {"version": 1, "disable_existing_loggers": False}
            json.dump(log_config, f)
            temp_path = f.name

        try:
            app = BoostApp(logger_config=temp_path)
            assert app._logger_config == log_config
        finally:
            os.unlink(temp_path)

    def test_init_with_logger_config_path_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            log_config = {"version": 1, "disable_existing_loggers": False}
            yaml.dump(log_config, f)
            temp_path = f.name

        try:
            app = BoostApp(logger_config=temp_path)
            assert app._logger_config == log_config
        finally:
            os.unlink(temp_path)

    def test_init_with_logger_config_path_ini(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                "[loggers]\nkeys=root\n\n[handlers]\nkeys=console\n\n[formatters]\nkeys=default\n\n"
                "[logger_root]\nlevel=DEBUG\nhandlers=console\n\n[handler_console]\n"
                "class=StreamHandler\nlevel=DEBUG\nformatter=default\n\n[formatter_default]\n"
                "format=%(asctime)s [%(levelname)s] %(name)s: %(message)s\n"
            )
            temp_path = f.name

        try:
            app = BoostApp(logger_config=temp_path)
            assert app._logger_config is None
        finally:
            os.unlink(temp_path)

    def test_init_with_invalid_logger_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json")
            temp_path = f.name

        try:
            with pytest.raises(RuntimeError, match="Logging configuration failed"):
                BoostApp(logger_config=temp_path)
        finally:
            os.unlink(temp_path)

    def test_get_registered_workers_empty(self):
        app = BoostApp()
        assert app.get_registered_workers() == []

    def test_add_worker_success(self):
        app = BoostApp()

        def dummy_activity():
            pass

        class DummyWorkflow:
            pass

        worker = app.add_worker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
            workflows=[DummyWorkflow],
        )

        assert isinstance(worker, TemporalBoostWorker)
        assert worker.name == "test_worker"
        assert len(app.get_registered_workers()) == 1

    def test_add_worker_with_reserved_name(self):
        app = BoostApp()

        def dummy_activity():
            pass

        with pytest.raises(RuntimeError, match="is reserved and cannot be used"):
            app.add_worker(
                worker_name="run",
                task_queue="test_queue",
                activities=[dummy_activity],
            )

    def test_add_worker_duplicate_name(self):
        app = BoostApp()

        def dummy_activity():
            pass

        app.add_worker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        with pytest.raises(RuntimeError, match="is already registered"):
            app.add_worker(
                worker_name="test_worker",
                task_queue="test_queue2",
                activities=[dummy_activity],
            )

    def test_add_worker_with_global_temporal_endpoint(self):
        app = BoostApp(temporal_endpoint="localhost:7233")

        def dummy_activity():
            pass

        worker = app.add_worker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        assert worker._client_builder is not None
        assert worker._client_builder._target_host == "localhost:7233"

    def test_add_worker_with_global_temporal_namespace(self):
        app = BoostApp(temporal_namespace="test_namespace")

        def dummy_activity():
            pass

        worker = app.add_worker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        assert worker._client_builder is not None
        assert worker._client_builder._namespace == "test_namespace"

    def test_add_worker_with_global_use_pydantic(self):
        app = BoostApp(use_pydantic=True)

        def dummy_activity():
            pass

        worker = app.add_worker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        assert worker._client_builder is not None
        assert worker._client_builder._data_converter is not None

    def test_add_worker_with_cron_schedule(self):
        app = BoostApp()

        def dummy_activity():
            pass

        async def cron_runner():
            pass

        worker = app.add_worker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
            cron_schedule="0 0 * * *",
            cron_runner=cron_runner,
        )

        assert app.get_registered_workers() == [worker]
        result = CliRunner().invoke(app._root_typer, ["cron", "test_worker", "--help"])
        assert result.exit_code == 0, result.exception
        assert "test_worker" in result.output

    def test_add_asgi_worker_success(self):
        app = BoostApp()

        class MockASGIApp:
            pass

        with patch("temporal_boost.boost_app.get_asgi_worker_class") as mock_get_worker:
            mock_worker_class = MagicMock()
            mock_worker_instance = MagicMock()
            mock_worker_instance.name = ""
            mock_worker_class.return_value = mock_worker_instance
            mock_get_worker.return_value = mock_worker_class

            app.add_asgi_worker(
                worker_name="asgi_worker",
                asgi_app=MockASGIApp(),
                host="0.0.0.0",
                port=8000,
            )

            assert len(app.get_registered_workers()) == 1
            mock_worker_class.assert_called_once()

    def test_add_asgi_worker_with_reserved_name(self):
        app = BoostApp()

        class MockASGIApp:
            pass

        with pytest.raises(RuntimeError, match="is reserved and cannot be used"):
            app.add_asgi_worker(
                worker_name="run",
                asgi_app=MockASGIApp(),
                host="0.0.0.0",
                port=8000,
            )

    def test_add_asgi_worker_duplicate_name(self):
        app = BoostApp()

        class MockASGIApp:
            pass

        with patch("temporal_boost.boost_app.get_asgi_worker_class") as mock_get_worker:
            mock_worker_class = MagicMock()
            mock_worker_instance = MagicMock()
            mock_worker_instance.name = ""
            mock_worker_class.return_value = mock_worker_instance
            mock_get_worker.return_value = mock_worker_class

            app.add_asgi_worker(
                worker_name="asgi_worker",
                asgi_app=MockASGIApp(),
                host="0.0.0.0",
                port=8000,
            )

            with pytest.raises(RuntimeError, match="is already registered"):
                app.add_asgi_worker(
                    worker_name="asgi_worker",
                    asgi_app=MockASGIApp(),
                    host="0.0.0.0",
                    port=8001,
                )

    def test_add_faststream_worker_success(self):
        app = BoostApp()

        class MockFastStreamApp:
            pass

        with patch("temporal_boost.boost_app.FastStreamBoostWorker") as mock_worker_class:
            mock_worker_instance = MagicMock()
            mock_worker_instance.name = ""
            mock_worker_class.return_value = mock_worker_instance

            worker = app.add_faststream_worker(
                worker_name="faststream_worker",
                faststream_app=MockFastStreamApp(),
            )

            assert len(app.get_registered_workers()) == 1
            mock_worker_class.assert_called_once()

    def test_add_faststream_worker_with_reserved_name(self):
        app = BoostApp()

        class MockFastStreamApp:
            pass

        with pytest.raises(RuntimeError, match="is reserved and cannot be used"):
            app.add_faststream_worker(
                worker_name="exec",
                faststream_app=MockFastStreamApp(),
            )

    def test_add_exec_method_sync(self):
        app = BoostApp()

        def exec_callback():
            return "executed"

        app.add_exec_method_sync("test_exec", exec_callback)
        assert app._exec_typer is not None

    def test_add_async_runtime(self):
        app = BoostApp()

        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        app.add_async_runtime("test_worker", worker)
        assert len(app.get_registered_workers()) == 1

    def test_add_async_runtime_with_reserved_name(self):
        app = BoostApp()

        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        with pytest.raises(RuntimeError, match="is reserved and cannot be used"):
            app.add_async_runtime("all", worker)

    def test_run_all_workers_no_workers(self):
        app = BoostApp()
        app.run_all_workers()
        assert len(app.get_registered_workers()) == 0

    def test_run_all_workers_with_workers(self):
        app = BoostApp()

        def dummy_activity():
            pass

        worker = app.add_worker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        with patch.object(worker, "run", side_effect=app.stop) as mock_run:
            app.run_all_workers()

            mock_run.assert_called_once()

    @pytest.mark.parametrize(
        "failure", [RuntimeError("worker failed"), KeyboardInterrupt(), SystemExit(7), asyncio.CancelledError()]
    )
    def test_worker_failure_stops_peer_and_reaches_caller(self, failure: BaseException) -> None:
        app = BoostApp(logger_config=None, shutdown_timeout=1.0)
        first = app.add_worker("failing", "queue", activities=[MagicMock()])
        peer = app.add_worker("peer", "queue", activities=[MagicMock()])
        ready, stopped, returned = threading.Event(), threading.Event(), threading.Event()

        def fail() -> None:
            assert ready.wait(3.0)
            raise failure

        def serve() -> None:
            ready.set()
            assert stopped.wait(3.0)
            returned.set()

        def request_stop() -> bool:
            stopped.set()
            return True

        with (
            patch.object(first, "run", side_effect=fail),
            patch.object(peer, "run", side_effect=serve),
            patch.object(peer, "request_stop", side_effect=request_stop) as stop,
        ):
            try:
                with pytest.raises(type(failure)) as raised:
                    app.run_all_workers()
            finally:
                stopped.set()

        assert raised.value is failure
        assert "fail" in [frame.name for frame in traceback.extract_tb(raised.value.__traceback__)]
        stop.assert_called_once()
        assert returned.is_set()

    def test_run_all_cli_observes_worker_failure(self) -> None:
        app = BoostApp(logger_config=None)
        worker = app.add_worker("failing", "queue", activities=[MagicMock()])
        failure = RuntimeError("worker failed")
        with patch.object(worker, "run", side_effect=failure) as run:
            result = CliRunner().invoke(app._root_typer, ["run", "all"])

        run.assert_called_once()
        assert result.exit_code == 1
        assert result.exception is failure

    def test_run_with_argument_list_dispatches_selected_worker(self) -> None:
        app = BoostApp(logger_config=None)
        worker = app.add_worker("selected", "queue", activities=[MagicMock()])
        other = app.add_worker("other", "queue", activities=[MagicMock()])

        with (
            patch.object(worker, "_run_worker", new_callable=AsyncMock) as selected_run,
            patch.object(other, "_run_worker", new_callable=AsyncMock) as other_run,
        ):
            with pytest.raises(SystemExit) as raised:
                app.run(["run", "selected"])

        assert raised.value.code == 0
        selected_run.assert_awaited_once()
        other_run.assert_not_awaited()

    def test_run_without_arguments_uses_sys_argv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        app = BoostApp(logger_config=None)
        worker = app.add_worker("selected", "queue", activities=[MagicMock()])
        monkeypatch.setattr(sys, "argv", ["main.py", "run", "selected"])

        with patch.object(worker, "_run_worker", new_callable=AsyncMock) as selected_run:
            with pytest.raises(SystemExit) as raised:
                app.run()

        assert raised.value.code == 0
        selected_run.assert_awaited_once()
