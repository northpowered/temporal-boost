# Base imports
import asyncio
import logging
import platform
import typing
from threading import Thread

import typer
from multiprocess import Process

from .asgi import ASGIWorker
from .logger import BoostLogger, BoostLoggerConfig
from .schemas import BoostOTLPConfig, ClientConnectorArgs
from .tracing import create_tracer, trace
from .worker import BoostWorker

PROHIBITED_WORKER_NAMES: list[str] = ["all", "internal_boost"]


class BoostApp:
    def __init__(  # noqa: PLR0913, PLR0917
        self,
        name: str = "temporal_generic_service",
        temporal_endpoint: str = "localhost:7233",
        temporal_namespace: str = "default",
        otlp_config: BoostOTLPConfig | None = None,
        logger_config: BoostLoggerConfig | None = None,
        logger: logging.Logger | None = None,
        use_pydantic: bool = False,  # noqa: FBT002
    ) -> None:
        self.name: str = name
        self.temporal_endpoint: str = temporal_endpoint
        self.temporal_namespace: str = temporal_namespace

        self.otlp_config: BoostOTLPConfig | None = otlp_config
        self.logger_config = logger_config

        self.use_pydantic: bool = use_pydantic
        # self.doc_config: DocServerConfig | None = doc_config  # noqa: ERA001

        # Logger creating logic:
        # Priority:
        # 1. Creating logger from default BoostLoggerConfig
        # 2. Creating logger from BoostLoggerConfig
        # 2. Using external logger
        if self.logger_config is None:
            self.logger: logging.Logger = BoostLogger().get_default_logger()
        elif logger is None:
            self.logger: logging.Logger = BoostLogger(config=self.logger_config).get_default_logger()
        else:
            self.logger: logging.Logger = logger

        self.registered_workers: list[BoostWorker] = []
        self.registered_cron_workers: list[BoostWorker] = []
        self.registered_asgi_workers: list[ASGIWorker] = []

        self.client_connector_args: ClientConnectorArgs = ClientConnectorArgs(
            temporal_endpoint=self.temporal_endpoint,
            temporal_namespace=self.temporal_namespace,
            otlp_config=self.otlp_config,
        )

        self._root_typer: typer.Typer = typer.Typer(name=self.name, no_args_is_help=True)
        # Typer for running workers
        self.run_typer: typer.Typer = typer.Typer(name="run")
        # Typer for running cron workflows
        self.cron_typer: typer.Typer = typer.Typer(name="cron")
        # Typer for separate commands (without runtime)
        self.exec_typer: typer.Typer = typer.Typer(name="exec")

        self._root_typer.add_typer(self.run_typer, no_args_is_help=True)
        self._root_typer.add_typer(self.cron_typer, no_args_is_help=True)
        self._root_typer.add_typer(self.exec_typer, no_args_is_help=True)

        self.run_typer.command(name="all")(self.register_all)

        # Creting OTLP tracer for an app
        self.tracer: trace.Tracer | None = None

        if self.otlp_config:
            # If `service_name` in OTLPConfig is None,
            # use app name
            service_name: str = self.otlp_config.service_name
            if not service_name:
                service_name = self.name
            # Create tracer and add it into the app
            self.tracer = create_tracer(service_name=service_name, otlp_endpoint=self.otlp_config.otlp_endpoint)

        # if self.doc_config:
        #     self.run_typer.command(name="doc")(serve_doc_page(self.doc_config))  # noqa: ERA001

    def add_worker(  # noqa: PLR0913, PLR0917
        self,
        worker_name: str,
        task_queue: str,
        workflows: list | None = None,
        activities: list | None = None,
        cron_schedule: str | None = None,
        cron_runner: typing.Coroutine | None = None,
        metrics_endpoint: str | None = None,
        description: str = "",
        **worker_kwargs: typing.Any,
    ) -> None:
        # Constraints check:
        if activities is None:
            activities = []
        if workflows is None:
            workflows = []
        if worker_name in PROHIBITED_WORKER_NAMES:
            raise RuntimeError(f"{worker_name} name for worker is reserved for temporal-boost")

        for registered_worker in self.registered_workers:
            if worker_name == registered_worker.name:
                raise RuntimeError(f"{worker_name} name for worker`s already reserved")

        worker: BoostWorker = BoostWorker(
            app=self,
            name=worker_name,
            client_connector_args=self.client_connector_args,
            task_queue=task_queue,
            workflows=workflows,
            activities=activities,
            cron_schedule=cron_schedule,
            cron_runner=cron_runner,
            metrics_endpoint=metrics_endpoint,
            description=description,
            **worker_kwargs,
        )
        # Add this worker to `run` section in CLI
        self.run_typer.command(name=worker_name)(worker.run)

        if cron_schedule and cron_runner:
            # If cron_schedule and cron_runner is not None
            # register this worker as cron_worker too
            self.cron_typer.command(name=worker_name)(worker.cron)
            self.registered_cron_workers.append(worker)

        self.registered_workers.append(worker)
        self.logger.info(f"Worker {worker_name} was registered in CLI")

    def add_internal_worker(
        self,
        host: str,
        port: int,
        doc_endpoint: str | None = "/doc",
        doc_css_endpoint: str | None = "/style.css",
        doc_js_endpoint: str | None = "/scripts.js",
    ) -> None:
        """
            Importing InternalWorker class only if needs in case of uncompatible
            dependencies of `robyn` package for Python3.13
        """
        from .internal import InternalWorker

        worker_name: str = "internal_boost"

        # While intrenal worker is fully HTTP without Temporal connection,
        # left `task_queue` hardcoded
        worker: InternalWorker = InternalWorker(
            self,
            task_queue="internal_queue",
            worker_name=worker_name,
            host=host,
            port=port,
            doc_endpoint=doc_endpoint,
            doc_css_endpoint=doc_css_endpoint,
            doc_js_endpoint=doc_js_endpoint,
        )

        self.run_typer.command(name=worker_name)(worker.run)
        self.registered_workers.append(worker)
        self.logger.info("Internal worker was registered in CLI")

    def add_asgi_worker(self, worker_name: str, asgi_app: typing.Any, host: str, port: int) -> None:
        # REDONE to .utils methods
        # Constraints check:
        if worker_name in PROHIBITED_WORKER_NAMES:
            raise RuntimeError(f"{worker_name} name for worker is reserved for temporal-boost")

        for registered_worker in self.registered_workers:
            if worker_name == registered_worker.name:
                raise RuntimeError(f"{worker_name} name for worker`s already reserved")

        worker: ASGIWorker = ASGIWorker(app=self, worker_name=worker_name, host=host, port=port, asgi_app=asgi_app)
        self.run_typer.command(name=worker_name)(worker.run)
        self.registered_workers.append(worker)
        self.registered_asgi_workers.append(worker)
        self.logger.info(f"ASGI worker {worker_name} was registered in CLI")

    def add_exec_method_sync(self, name: str, callback: typing.Callable) -> None:
        self.exec_typer.command(name=name)(callback)

    def add_async_runtime(self, name: str, runtime: BoostWorker) -> None:
        self.run_typer.command(name=name)(runtime.run)
        self.registered_workers.append(runtime)
        self.logger.info(f"Async runtime {name} was registered in CLI")

    def run(self) -> None:
        asyncio.run(self._root_typer())

    def register_all(self) -> None:
        if platform.system() == "Windows":
            self.logger.warning("Use all-in-one mode only in development! You are working via Threads")
            threads: list[Thread] = []

            # Make threads
            for worker in self.registered_workers:
                thread = Thread(
                    target=worker.run,
                )
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()
        else:
            self.logger.warning("Use all-in-one mode only in development!")
            procs: list[Process] = []
            # Creating worker
            for worker in self.registered_workers:
                proc = Process(
                    target=worker.run,
                )
                procs.append(proc)
                proc.start()

            for proc in procs:
                proc.join()
