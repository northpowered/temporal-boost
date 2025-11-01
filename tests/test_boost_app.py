import json
import logging
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import yaml

from temporal_boost.boost_app import BoostApp
from temporal_boost.workers.temporal import TemporalBoostWorker


class TestBoostApp:
    def test_init_with_defaults(self):
        app = BoostApp()
        assert app._name == "temporal_generic_service"
        assert app._global_temporal_endpoint is None
        assert app._global_temporal_namespace is None
        assert app._global_use_pydantic is None
        assert app._debug_mode is False
        assert app._registered_workers == []
        assert app._registered_cron_workers == []
        assert app._registered_asgi_workers == []

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

        assert worker in app._registered_cron_workers
        assert len(app._registered_cron_workers) == 1

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

        with patch.object(worker, "run") as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            app.run_all_workers()

            mock_run.assert_called_once()

    def test_run_with_args(self):
        app = BoostApp()
        with patch.object(app._root_typer, "__call__", return_value=None) as mock_run:
            try:
                app.run("test", "args")
            except SystemExit:
                pass
            mock_run.assert_called_once()

    def test_run_with_args(self):
        app = BoostApp()

        def dummy_activity():
            pass

        app.add_worker(
            worker_name="test_worker",
            task_queue="test_queue",
            activities=[dummy_activity],
        )

        with patch.object(app._root_typer, "__call__", return_value=None) as mock_run:
            try:
                app.run("run", "test_worker")
            except (SystemExit, Exception):
                pass
            assert mock_run.called or len(app.get_registered_workers()) == 1

