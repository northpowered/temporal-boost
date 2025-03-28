import json
import logging
import logging.config
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
import yaml
from temporalio.types import MethodAsyncNoParam
from temporalio.worker._interceptor import Interceptor

from temporal_boost._loops import Loops, loops
from temporal_boost.common import DEFAULT_LOGGING_CONFIG
from temporal_boost.workers import (
    ASGIWorkerType,
    BaseAsgiWorker,
    BaseBoostWorker,
    TemporalBoostWorker,
    get_asgi_worker_class,
)


logger = logging.getLogger(__name__)


class BoostApp:
    def __init__(  # noqa: PLR0913
        self,
        name: str | None = None,
        loop_impl: Loops = Loops.auto,
        *,
        temporal_endpoint: str | None = None,
        temporal_namespace: str | None = None,
        debug_mode: bool = False,
        use_pydantic: bool | None = None,
        logger_config: dict[str, Any] | str | Path | None = DEFAULT_LOGGING_CONFIG,
    ) -> None:
        self._name: str = name or "temporal_generic_service"
        self._loop_impl = loop_impl

        self._global_temporal_endpoint = temporal_endpoint
        self._global_temporal_namespace = temporal_namespace
        self._global_use_pydantic = use_pydantic

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
        **worker_kwargs: Any,
    ) -> TemporalBoostWorker:
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
            debug_mode=self._debug_mode,
            **worker_kwargs,
        )
        worker.configure_temporal_client(
            target_host=self._global_temporal_endpoint,
            namespace=self._global_temporal_namespace,
        )

        if self._global_use_pydantic is not None:
            worker.configure_temporal_client(use_pydantic_data_converter=self._global_use_pydantic)

        self._run_typer.command(name=worker_name)(worker.run)

        if cron_schedule and cron_runner:
            self._cron_typer.command(name=worker_name)(worker.cron)
            self._registered_cron_workers.append(worker)

        self._registered_workers.append(worker)
        logger.info(f"Worker '{worker_name}' was registered in CLI.")
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
        for registered_worker in self._registered_workers:
            if worker_name == registered_worker.name:
                raise RuntimeError(f"{worker_name} name for worker`s already reserved")

        AsgiWorkerClass = get_asgi_worker_class(asgi_worker_type)  # noqa: N806
        worker = AsgiWorkerClass(
            app=asgi_app,
            host=host,
            port=port,
            log_level=log_level,
            **asgi_worker_kwargs,
        )

        self._run_typer.command(name=worker_name)(worker.run)
        self._registered_workers.append(worker)
        self._registered_asgi_workers.append(worker)
        logger.info(f"ASGI worker {worker_name} was registered in CLI")

    def add_exec_method_sync(self, name: str, callback: Callable[..., Any]) -> None:
        self._exec_typer.command(name=name)(callback)

    def add_async_runtime(self, worker_name: str, boost_worker: TemporalBoostWorker) -> None:
        for registered_worker in self._registered_workers:
            if worker_name == registered_worker.name:
                raise RuntimeError(f"{worker_name} name for worker`s already reserved")

        self._run_typer.command(name=worker_name)(boost_worker.run)
        self._registered_workers.append(boost_worker)
        logger.info(f"Async runtime {worker_name} was registered in CLI")

    def run(self, *args: Any, **kwargs: Any) -> None:
        self._loop = loops.get(self._loop_impl)
        self._loop.run_until_complete(self._root_typer(*args, **kwargs))

    @staticmethod
    def _configure_logging(log_config: dict[str, Any] | Path | None) -> None:
        try:
            if isinstance(log_config, dict):
                logging.config.dictConfig(log_config)
            elif isinstance(log_config, Path):
                if log_config.suffix in {".json", ".yaml", ".yml"}:
                    loader = json.loads if log_config.suffix == ".json" else yaml.safe_load
                    log_conf = loader(log_config.read_text())
                    logging.config.dictConfig(log_conf)
                else:
                    logging.config.fileConfig(log_config.as_posix(), disable_existing_loggers=False)
            logger.debug("Logging configured successfully.")
        except Exception as exc:
            logger.exception("Failed to configure logging")
            raise RuntimeError(f"Logging configuration failed: {exc}") from exc
