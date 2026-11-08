import json
import logging
import logging.config
import math
import sys
import threading
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, ClassVar

import typer
import yaml
from temporalio.types import MethodAsyncNoParam
from temporalio.worker._interceptor import Interceptor

from temporal_boost.cli.process_context import validate_asgi_processes
from temporal_boost.common import DEFAULT_LOGGING_CONFIG
from temporal_boost.worker_coordinator import WorkerCoordinator
from temporal_boost.workers import (
    ASGIWorkerType,
    BaseAsgiWorker,
    BaseBoostWorker,
    FastStreamBoostWorker,
    TemporalBoostWorker,
    get_asgi_worker_class,
)


logger = logging.getLogger(__name__)


class BoostApp:
    _RESERVED_NAMES: ClassVar[set[str]] = {"run", "cron", "exec", "all"}

    def __init__(  # noqa: PLR0913
        self,
        name: str | None = None,
        *,
        temporal_endpoint: str | None = None,
        temporal_namespace: str | None = None,
        debug_mode: bool = False,
        use_pydantic: bool | None = None,
        logger_config: dict[str, Any] | str | Path | None = DEFAULT_LOGGING_CONFIG,
        shutdown_timeout: float = 30.0,
    ) -> None:
        if not math.isfinite(shutdown_timeout) or shutdown_timeout < 0:
            raise ValueError("shutdown_timeout must be a finite, non-negative number of seconds")
        self._shutdown_timeout = shutdown_timeout
        self._worker_coordinator: WorkerCoordinator | None = None
        self._run_lock = threading.Lock()
        self._name: str = name or "temporal_generic_service"

        self._global_temporal_endpoint = temporal_endpoint
        self._global_temporal_namespace = temporal_namespace
        self._global_use_pydantic = use_pydantic

        self._logger_config: dict[str, Any] | None = None
        log_config = Path(logger_config) if isinstance(logger_config, str) else logger_config
        self._configure_logging(log_config)

        self._debug_mode = debug_mode

        self._registered_workers: list[BaseBoostWorker] = []
        self._registered_cron_workers: list[BaseBoostWorker] = []
        self._registered_asgi_workers: list[BaseAsgiWorker] = []

        self._root_typer = typer.Typer(name=self._name, no_args_is_help=True)
        self._run_typer = typer.Typer(name="run")
        self._cron_typer = typer.Typer(name="cron")
        self._exec_typer: typer.Typer = typer.Typer(name="exec")

        self._root_typer.add_typer(self._run_typer, no_args_is_help=True)
        self._root_typer.add_typer(self._cron_typer, no_args_is_help=True)
        self._root_typer.add_typer(self._exec_typer, no_args_is_help=True)

        self._run_typer.command(name="all")(self._run_all_workers_cli)

    def add_worker(  # noqa: PLR0913
        self,
        worker_name: str,
        task_queue: str,
        *,
        activities: list[Callable[..., Any]] | None = None,
        workflows: list[type] | None = None,
        interceptors: list[Interceptor] | None = None,
        cron_schedule: str | None = None,
        cron_runner: MethodAsyncNoParam[Any, Any] | None = None,
        cron_workflow_id: str | None = None,
        **worker_kwargs: Any,
    ) -> TemporalBoostWorker:
        if worker_name in self._RESERVED_NAMES:
            raise RuntimeError(f"Worker name '{worker_name}' is reserved and cannot be used.")

        for registered_worker in self._registered_workers:
            if worker_name == getattr(registered_worker, "name", None):
                raise RuntimeError(f"Worker name '{worker_name}' is already registered.")

        worker = TemporalBoostWorker(
            worker_name=worker_name,
            task_queue=task_queue,
            workflows=workflows,
            activities=activities,
            interceptors=interceptors,
            cron_schedule=cron_schedule,
            cron_runner=cron_runner,
            cron_workflow_id=cron_workflow_id,
            debug_mode=self._debug_mode,
            **worker_kwargs,
        )
        worker.configure_temporal_client(
            target_host=self._global_temporal_endpoint,
            namespace=self._global_temporal_namespace,
            use_pydantic_data_converter=self._global_use_pydantic,
        )

        self._run_typer.command(name=worker_name)(self._worker_run_command(worker))

        if cron_schedule is not None and cron_runner is not None:
            self._cron_typer.command(name=worker_name)(worker.cron)
            self._registered_cron_workers.append(worker)

        self._registered_workers.append(worker)
        return worker

    def add_asgi_worker(  # noqa: PLR0913
        self,
        worker_name: str,
        asgi_app: Any,
        host: str,
        port: int,
        *,
        log_level: str | int | None = None,
        asgi_worker_type: ASGIWorkerType = ASGIWorkerType.auto,
        **asgi_worker_kwargs: Any,
    ) -> None:
        if worker_name in self._RESERVED_NAMES:
            raise RuntimeError(f"Worker name '{worker_name}' is reserved and cannot be used.")

        for registered_worker in self._registered_workers:
            if worker_name == registered_worker.name:
                raise RuntimeError(f"Worker name '{worker_name}' is already registered.")

        AsgiWorkerClass = get_asgi_worker_class(asgi_worker_type)  # noqa: N806
        worker = AsgiWorkerClass(
            app=asgi_app,
            host=host,
            port=port,
            log_level=log_level,
            log_config=self._logger_config,
            **asgi_worker_kwargs,
        )

        worker.name = worker_name

        self._run_typer.command(name=worker_name)(self._worker_run_command(worker))
        self._registered_workers.append(worker)

    def add_faststream_worker(
        self,
        worker_name: str,
        faststream_app: Any,
        *,
        log_level: str | int | None = None,
        **faststream_kwargs: Any,
    ) -> FastStreamBoostWorker:
        if worker_name in self._RESERVED_NAMES:
            raise RuntimeError(f"Worker name '{worker_name}' is reserved and cannot be used.")

        for registered_worker in self._registered_workers:
            if worker_name == registered_worker.name:
                raise RuntimeError(f"Worker name '{worker_name}' is already registered.")

        worker = FastStreamBoostWorker(
            app=faststream_app,
            log_level=log_level,
            **faststream_kwargs,
        )

        worker.name = worker_name

        self._run_typer.command(name=worker_name)(self._worker_run_command(worker))
        self._registered_workers.append(worker)
        return worker

    def add_exec_method_sync(self, name: str, callback: Callable[..., Any]) -> None:
        self._exec_typer.command(name=name)(callback)

    def add_async_runtime(self, worker_name: str, boost_worker: BaseBoostWorker) -> None:
        if worker_name in self._RESERVED_NAMES:
            raise RuntimeError(f"Worker name '{worker_name}' is reserved and cannot be used.")

        for registered_worker in self._registered_workers:
            if worker_name == registered_worker.name:
                raise RuntimeError(f"Worker name '{worker_name}' is already registered.")

        self._run_typer.command(name=worker_name)(self._worker_run_command(boost_worker))
        self._registered_workers.append(boost_worker)

    def _worker_run_command(self, worker: BaseBoostWorker) -> Callable[..., Any]:
        run = worker.run
        if not isinstance(worker, BaseAsgiWorker):
            return run

        @wraps(run)
        def run_asgi(*args: Any, **kwargs: Any) -> Any:
            validate_asgi_processes([worker])
            return run(*args, **kwargs)

        return run_asgi

    def get_registered_workers(self) -> list[BaseBoostWorker]:
        return self._registered_workers.copy()

    def run_all_workers(self) -> None:
        """Run all consumers without registering CRON workflows.

        Raises:
            RuntimeError: If another run is active or a worker fails.
        """
        if not self._registered_workers:
            logger.warning("No workers registered to run")
            return

        logger.info(f"Starting {len(self._registered_workers)} workers in separate threads")

        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("Application workers are already running")
        try:
            if self._worker_coordinator is not None and self._worker_coordinator.is_alive():
                raise RuntimeError("Workers from the previous run are still running")
            self._worker_coordinator = WorkerCoordinator(self.get_registered_workers(), self._shutdown_timeout)
            self._worker_coordinator.run()
        finally:
            self._run_lock.release()

    def _run_all_workers_cli(self) -> None:
        """Run all consumers without registering CRON workflows.

        Raises:
            RuntimeError: If a worker fails with a success exit code.
            SystemExit: If a worker requests a nonzero exit code.
        """
        validate_asgi_processes(self.get_registered_workers())
        try:
            self.run_all_workers()
        except SystemExit as exc:
            # The coordinator treats every worker exception as a failure. A
            # worker's SystemExit(0) must not turn that failure into CLI success.
            if exc.code is None or exc.code == 0:
                raise RuntimeError("A worker raised SystemExit with a success code during run all") from exc
            raise

    def stop(self) -> None:
        """Request that the current run_all_workers() stop; safe from any thread.

        This is non-blocking and idempotent. Before/after a run it has no effect.
        Wait for run_all_workers() to return to observe completion or timeout.
        """
        coordinator = self._worker_coordinator
        if coordinator is not None:
            coordinator.request_stop()

    def run(self, args: list[str] | None = None, **kwargs: Any) -> Any:
        """Invoke the CLI, preserving exits; use standalone_mode=False for embedding.

        Args:
            args: One argument list, or None to use sys.argv[1:]. An empty list stays empty.
            **kwargs: Options forwarded to Typer, including standalone_mode and prog_name.

        Returns:
            The command result when standalone_mode=False; otherwise Typer raises SystemExit.

        Raises:
            TypeError: If arguments are passed as a string instead of a list.
        """
        if isinstance(args, str):
            raise TypeError("CLI arguments must be passed as one list of strings")
        typer_args = sys.argv[1:] if args is None else list(args)

        if len(typer_args) > 1:
            logger.info(f"Application '{self._name}' is starting. Selected worker: '{typer_args[1]}'")
        else:
            logger.info(f"Application '{self._name}' is starting. No specific worker selected.")

        try:
            # Leave argv reading/Windows expansion to Click when args is None.
            return self._root_typer(args=None if args is None else typer_args, **kwargs)
        except Exception:
            logger.exception("Error during application run")
            raise

    def _configure_logging(self, log_config: dict[str, Any] | Path | None) -> None:
        try:
            if isinstance(log_config, dict):
                self._logger_config = log_config
                logging.config.dictConfig(log_config)
            elif isinstance(log_config, Path):
                if log_config.suffix in {".json", ".yaml", ".yml"}:
                    loader = json.loads if log_config.suffix == ".json" else yaml.safe_load
                    log_conf = loader(log_config.read_text())
                    self._logger_config = log_conf
                    logging.config.dictConfig(log_conf)
                else:
                    logging.config.fileConfig(log_config.as_posix(), disable_existing_loggers=False)
            logger.debug("Logging configured successfully.")
        except Exception as exc:
            logger.exception("Failed to configure logging")
            raise RuntimeError(f"Logging configuration failed: {exc}") from exc
