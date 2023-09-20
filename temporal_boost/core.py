# Base imports
import typer
import asyncio
import typing
from multiprocessing import Process
# Local imports
from .worker import BoostWorker
from .schemas import ClientConnectorArgs, BoostOTLPConfig
from .tracing import create_tracer, trace
from .logger import BoostLogger, BoostLoggerConfig
import logging


PROHIBITED_WORKER_NAMES: list[str] = ['all']


class BoostApp:
    def __init__(
        self,
        name: str = "temporal_generic_service",
        temporal_endpoint: str = "localhost:7233",
        temporal_namespace: str = "default",
        otlp_config: BoostOTLPConfig | None = None,
        logger_config: BoostLoggerConfig | None = None,
        logger: logging.Logger | None = None

    ) -> None:
        self.name: str = name
        self.temporal_endpoint: str = temporal_endpoint
        self.temporal_namespace: str = temporal_namespace

        self.otlp_config: BoostOTLPConfig | None = otlp_config
        self.logger_config = logger_config

        # Logger creating logic:
        # Priority:
        # 1. Creating logger from default BoostLoggerConfig
        # 2. Creating logger from BoostLoggerConfig
        # 2. Using external logger
        if self.logger_config is None:
            self.logger: logging.Logger = BoostLogger().get_default_logger()
        else:
            if logger is None:
                self.logger: logging.Logger = BoostLogger(config=self.logger_config).get_default_logger()
            else:
                self.logger: logging.Logger = logger

        self.registered_workers: list[BoostWorker] = []
        self.registered_cron_workers: list[BoostWorker] = []

        self.client_connector_args: ClientConnectorArgs = ClientConnectorArgs(
            temporal_endpoint=self.temporal_endpoint,
            temporal_namespace=self.temporal_namespace,
            otlp_config=self.otlp_config
        )

        self._root_typer: typer.Typer = typer.Typer(
            name=self.name,
            no_args_is_help=True
        )
        self.run_typer: typer.Typer = typer.Typer(
            name="run"
        )

        self.cron_typer: typer.Typer = typer.Typer(
            name="cron"
        )

        self._root_typer.add_typer(self.run_typer, no_args_is_help=True)
        self._root_typer.add_typer(self.cron_typer, no_args_is_help=True)

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
            self.tracer = create_tracer(
                service_name=service_name,
                otlp_endpoint=self.otlp_config.otlp_endpoint
            )

    def add_worker(
        self,
        worker_name: str,
        task_queue: str,
        workflows: list = [],
        activities: list = [],
        cron_schedule: str | None = None,
        cron_runner: typing.Coroutine | None = None,
        metrics_endpoint: str | None = None
    ) -> None:

        # Constraints check:
        if worker_name in PROHIBITED_WORKER_NAMES:
            raise RuntimeError(
                f"{worker_name} name for worker is reserved for temporal-boost"
            )

        for registered_worker in self.registered_workers:
            if worker_name == registered_worker.name:
                raise RuntimeError(
                    f"{worker_name} name for worker`s already reserved"
                )

        worker: BoostWorker = BoostWorker(
            app=self,
            name=worker_name,
            client_connector_args=self.client_connector_args,
            task_queue=task_queue,
            workflows=workflows,
            activities=activities,
            cron_schedule=cron_schedule,
            cron_runner=cron_runner,
            metrics_endpoint=metrics_endpoint
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

    def run(self):
        asyncio.run(self._root_typer())

    def register_all(self):

        self.logger.warning('Use all-in-one mode only in development!')
        procs: list[Process] = list()
        # Creating worker
        for worker in self.registered_workers:

            proc = Process(
                target=worker.run,
            )
            procs.append(proc)
            proc.start()

        for proc in procs:
            proc.join()
