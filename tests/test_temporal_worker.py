import importlib.util
import logging
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.converter import DataConverter

from temporal_boost import BoostApp
from temporal_boost.temporal import config
from temporal_boost.temporal.worker import TemporalWorkerBuilder
from temporal_boost.workers.temporal import TemporalBoostWorker


class TestTemporalWorkerBuilder:
    @pytest.mark.parametrize(
        ("env_value", "expected"),
        [(None, 30), ("65", 65), ("0", 0), ("invalid", 30), ("-1", None)],
    )
    def test_graceful_shutdown_timeout_from_environment(
        self, monkeypatch: pytest.MonkeyPatch, env_value: str | None, expected: int | None
    ) -> None:
        if env_value is None:
            monkeypatch.delenv("TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT", raising=False)
        else:
            monkeypatch.setenv("TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT", env_value)
        # Execute config in a separate module without reloading shared imports.
        spec = importlib.util.spec_from_file_location("isolated_worker_config", config.__file__)
        assert spec is not None
        assert spec.loader is not None
        isolated_config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(isolated_config)
        monkeypatch.setattr("temporal_boost.temporal.worker.config", isolated_config)

        if expected is None:
            with pytest.raises(ValueError, match="graceful_shutdown_timeout.*non-negative"):
                TemporalWorkerBuilder("queue")
            return

        builder = TemporalWorkerBuilder("queue")
        builder.set_client(MagicMock())
        with patch("temporal_boost.temporal.worker.Worker") as sdk_worker:
            builder.build()

        assert sdk_worker.call_args.kwargs["graceful_shutdown_timeout"] == timedelta(seconds=expected)

    @pytest.mark.parametrize(
        ("env_seconds", "explicit", "expected"),
        [
            (70, None, timedelta(seconds=70)),
            (0, None, timedelta()),
            (70, timedelta(), timedelta()),
            (70, timedelta(seconds=2.5), timedelta(seconds=2.5)),
            (-1, timedelta(), timedelta()),
        ],
    )
    def test_graceful_shutdown_timeout_override(
        self, monkeypatch: pytest.MonkeyPatch, env_seconds: int, explicit: timedelta | None, expected: timedelta
    ) -> None:
        monkeypatch.setattr(config, "GRACEFUL_SHUTDOWN_TIMEOUT", timedelta(seconds=env_seconds))
        builder = TemporalWorkerBuilder("queue", graceful_shutdown_timeout=explicit)
        builder.set_client(MagicMock())
        with patch("temporal_boost.temporal.worker.Worker") as sdk_worker:
            builder.build()

        assert sdk_worker.call_args.kwargs["graceful_shutdown_timeout"] == expected

    @pytest.mark.parametrize("timeout", [timedelta(seconds=-1), timedelta(microseconds=-1)])
    def test_negative_graceful_shutdown_timeout_is_rejected(self, timeout: timedelta) -> None:
        with pytest.raises(ValueError, match="graceful_shutdown_timeout.*non-negative"):
            TemporalWorkerBuilder("queue", graceful_shutdown_timeout=timeout)

    def test_init_with_defaults(self):
        builder = TemporalWorkerBuilder(task_queue="test_queue")
        assert builder.task_queue == "test_queue"
        assert builder._client is None
        assert builder._activities == []
        assert builder._workflows == []
        assert builder._interceptors == []
        assert builder._debug_mode is False

    def test_init_with_debug_mode(self):
        builder = TemporalWorkerBuilder(task_queue="test_queue", debug_mode=True)
        assert builder._debug_mode is True

    def test_init_with_max_concurrent_workflow_tasks(self):
        builder = TemporalWorkerBuilder(task_queue="test_queue", max_concurrent_workflow_tasks=100)
        assert builder._max_concurrent_workflow_tasks == 100

    def test_init_with_max_concurrent_activities(self):
        builder = TemporalWorkerBuilder(task_queue="test_queue", max_concurrent_activities=50)
        assert builder._max_concurrent_activities == 50

    def test_init_with_kwargs(self):
        builder = TemporalWorkerBuilder(task_queue="test_queue", custom_param="value")
        assert builder._worker_kwargs["custom_param"] == "value"

    def test_client_property_not_set(self):
        builder = TemporalWorkerBuilder(task_queue="test_queue")
        with pytest.raises(RuntimeError):
            _ = builder.client

    def test_client_property_set(self):
        builder = TemporalWorkerBuilder(task_queue="test_queue")
        mock_client = MagicMock()
        builder.set_client(mock_client)
        assert builder.client == mock_client

    def test_set_client(self):
        builder = TemporalWorkerBuilder(task_queue="test_queue")
        mock_client = MagicMock()
        builder.set_client(mock_client)
        assert builder._client == mock_client

    def test_set_activities(self):
        builder = TemporalWorkerBuilder(task_queue="test_queue")

        def activity1():
            pass

        def activity2():
            pass

        builder.set_activities([activity1, activity2])
        assert builder._activities == [activity1, activity2]

    def test_set_workflows(self):
        builder = TemporalWorkerBuilder(task_queue="test_queue")

        class Workflow1:
            pass

        class Workflow2:
            pass

        builder.set_workflows([Workflow1, Workflow2])
        assert builder._workflows == [Workflow1, Workflow2]

    def test_set_interceptors(self):
        builder = TemporalWorkerBuilder(task_queue="test_queue")
        interceptor1 = MagicMock()
        interceptor2 = MagicMock()

        builder.set_interceptors([interceptor1, interceptor2])
        assert builder._interceptors == [interceptor1, interceptor2]

    def test_build(self):
        builder = TemporalWorkerBuilder(task_queue="test_queue")
        mock_client = MagicMock()
        builder.set_client(mock_client)

        def activity():
            pass

        class Workflow:
            pass

        builder.set_activities([activity])
        builder.set_workflows([Workflow])

        with patch("temporal_boost.temporal.worker.Worker") as mock_worker_class:
            mock_worker_instance = MagicMock()
            mock_worker_class.return_value = mock_worker_instance

            worker = builder.build()

            assert worker == mock_worker_instance
            mock_worker_class.assert_called_once()
            call_kwargs = mock_worker_class.call_args[1]
            assert call_kwargs["client"] == mock_client
            assert call_kwargs["task_queue"] == "test_queue"
            assert call_kwargs["activities"] == [activity]
            assert call_kwargs["workflows"] == [Workflow]


class TestTemporalBoostWorker:
    @pytest.mark.parametrize("timeout", [None, timedelta(), timedelta(seconds=90)])
    def test_app_forwards_graceful_shutdown_timeout(
        self, monkeypatch: pytest.MonkeyPatch, timeout: timedelta | None
    ) -> None:
        monkeypatch.setattr(config, "GRACEFUL_SHUTDOWN_TIMEOUT", timedelta(seconds=55))
        app = BoostApp(logger_config=None)
        worker = app.add_worker(
            "worker",
            "queue",
            activities=[MagicMock()],
            graceful_shutdown_timeout=timeout,
            max_cached_workflows=123,
        )
        worker._worker_builder.set_client(MagicMock())
        with patch("temporal_boost.temporal.worker.Worker") as sdk_worker:
            result = worker._worker_builder.build()

        sdk_worker.assert_called_once()
        assert result is sdk_worker.return_value
        assert sdk_worker.call_args.kwargs["graceful_shutdown_timeout"] == (
            timedelta(seconds=55) if timeout is None else timeout
        )
        assert sdk_worker.call_args.kwargs["max_cached_workflows"] == 123

    def test_app_rejects_negative_graceful_shutdown_timeout(self) -> None:
        app = BoostApp(logger_config=None)
        with pytest.raises(ValueError, match="graceful_shutdown_timeout.*non-negative"):
            app.add_worker("worker", "queue", activities=[MagicMock()], graceful_shutdown_timeout=timedelta(seconds=-1))

    @pytest.mark.asyncio
    @pytest.mark.parametrize("env_enabled", [False, True])
    @pytest.mark.parametrize("use_pydantic", [None, False, True])
    async def test_configure_pydantic_override_matrix(
        self, monkeypatch: pytest.MonkeyPatch, env_enabled: bool, use_pydantic: bool | None
    ) -> None:
        monkeypatch.setattr(config, "USE_PYDANTIC_DATA_CONVERTER", env_enabled)
        worker = TemporalBoostWorker("test_worker", "test_queue", activities=[MagicMock()])
        worker.configure_temporal_client(use_pydantic_data_converter=use_pydantic)

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
    @pytest.mark.parametrize("custom_converter", [False, True])
    async def test_reconfigure_pydantic_after_build(
        self, monkeypatch: pytest.MonkeyPatch, custom_converter: bool
    ) -> None:
        monkeypatch.setattr(config, "USE_PYDANTIC_DATA_CONVERTER", True)
        worker = TemporalBoostWorker("test_worker", "test_queue", activities=[MagicMock()])
        converter = DataConverter()
        kwargs = {"data_converter": converter} if custom_converter else {}
        worker.configure_temporal_client(use_pydantic_data_converter=True, **kwargs)

        with (
            patch("temporalio.client.Client.connect", new_callable=AsyncMock) as connect,
            patch.object(worker._worker_builder, "build"),
        ):
            await worker._build_worker()
            worker.configure_temporal_client(use_pydantic_data_converter=False)
            await worker._build_worker()
            worker.configure_temporal_client(namespace="updated")
            await worker._build_worker()

        assert connect.call_args_list[0].kwargs["data_converter"] is (
            converter if custom_converter else pydantic_data_converter
        )
        for call in connect.call_args_list[1:]:
            if custom_converter:
                assert call.kwargs["data_converter"] is converter
            else:
                assert "data_converter" not in call.kwargs
        assert connect.call_args.kwargs["namespace"] == "updated"

    def test_init_with_minimal_params(self):
        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        assert worker.name == "test_worker"
        assert worker._worker_builder.task_queue == "test_queue"
        assert worker._worker is None
        assert worker._client is None
        assert worker._client_builder is None

    def test_init_with_no_workflows_or_activities(self):
        with pytest.raises(RuntimeError, match="must have at least one workflow or activity"):
            TemporalBoostWorker(
                worker_name="test_worker",
                task_queue="test_queue",
                activities=[],
                workflows=[],
            )

    def test_init_with_workflows_only(self):
        class DummyWorkflow:
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            workflows=[DummyWorkflow],
        )

        assert worker.name == "test_worker"

    def test_init_with_cron_schedule(self):
        def dummy_activity():
            pass

        async def cron_runner():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
            cron_schedule="0 0 * * *",
            cron_runner=cron_runner,
        )

        assert worker._cron_schedule == "0 0 * * *"
        assert worker._cron_runner == cron_runner

    def test_init_with_debug_mode(self):
        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
            debug_mode=True,
        )

        assert worker._worker_builder._debug_mode is True

    def test_init_with_interceptors(self):
        def dummy_activity():
            pass

        interceptor = MagicMock()

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
            interceptors=[interceptor],
        )

        assert interceptor in worker._worker_builder._interceptors

    def test_temporal_client_property_not_initialized(self):
        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        with pytest.raises(RuntimeError, match="Temporal client has not been initialized"):
            _ = worker.temporal_client

    def test_temporal_worker_property_not_initialized(self):
        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        with pytest.raises(RuntimeError, match="Temporal worker has not been initialized"):
            _ = worker.temporal_worker

    def test_temporal_cron_runner_property_not_set(self):
        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        with pytest.raises(RuntimeError, match="Cron runner is not configured"):
            _ = worker.temporal_cron_runner

    def test_temporal_cron_runner_property_set(self):
        def dummy_activity():
            pass

        async def cron_runner():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
            cron_runner=cron_runner,
        )

        assert worker.temporal_cron_runner == cron_runner

    def test_configure_temporal_client(self):
        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        worker.configure_temporal_client(
            target_host="localhost:7233",
            namespace="test_namespace",
            api_key="test_key",
            identity="test_identity",
            tls=True,
        )

        assert worker._client_builder is not None
        assert worker._client_builder._target_host == "localhost:7233"
        assert worker._client_builder._namespace == "test_namespace"
        assert worker._client_builder._api_key == "test_key"
        assert worker._client_builder._identity == "test_identity"
        assert worker._client_builder._tls is True

    def test_configure_temporal_client_pydantic(self):
        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        worker.configure_temporal_client(use_pydantic_data_converter=True)

        assert worker._client_builder is not None
        assert worker._client_builder._data_converter is not None

    def test_configure_temporal_client_updates_existing(self):
        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        worker.configure_temporal_client(target_host="localhost:7233")
        worker.configure_temporal_client(target_host="new_host:7233")

        assert worker._client_builder._target_host == "new_host:7233"

    def test_configure_temporal_runtime(self):
        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        worker.configure_temporal_runtime(
            prometheus_bind_address="0.0.0.0:9090",
            prometheus_counters_total_suffix=True,
        )

        assert worker._runtime_builder is not None
        assert worker._runtime_builder._prometheus_bind_address == "0.0.0.0:9090"
        assert worker._runtime_builder._prometheus_counters_total_suffix is True

    def test_temporal_client_runtime_property(self):
        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        runtime = worker.temporal_client_runtime
        assert runtime is not None

    @pytest.mark.asyncio
    async def test_build_worker(self):
        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        worker.configure_temporal_client(target_host="localhost:7233")

        mock_client = AsyncMock()
        mock_worker = MagicMock()

        with patch.object(worker._client_builder, "build", new_callable=AsyncMock) as mock_client_build:
            mock_client_build.return_value = mock_client

            with patch.object(worker._worker_builder, "build") as mock_worker_build:
                mock_worker_build.return_value = mock_worker

                await worker._build_worker()

                assert worker._client == mock_client
                assert worker._worker == mock_worker

    @pytest.mark.asyncio
    async def test_shutdown(self):
        def dummy_activity():
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        await worker.shutdown()
        await worker.shutdown()
        assert worker._worker is None

    def test_log_worker_start(self, caplog):
        def dummy_activity():
            pass

        class DummyWorkflow:
            pass

        worker = TemporalBoostWorker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
            workflows=[DummyWorkflow],
        )

        with caplog.at_level(logging.INFO):
            worker._log_worker_start()

        assert "Worker 'test_worker' started" in caplog.text
        assert "test_queue" in caplog.text
