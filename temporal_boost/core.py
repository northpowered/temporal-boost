# Base imports
import typer
import asyncio
import typing
from multiprocessing import Process
# Local imports
from .worker import BoostWorker
from .schemas import ClientConnectorArgs


PROHIBITED_WORKER_NAMES: list[str] = ['all']


class BoostApp:
    def __init__(
        self,
        name: str = "temporal_generic_service",
        temporal_endpoint: str = "localhost:7233",
        temporal_namespace: str = "default",
        enable_otlp: bool = True,
    ) -> None:
        self.name: str = name
        self.temporal_endpoint: str = temporal_endpoint
        self.temporal_namespace: str = temporal_namespace
        self.enable_otlp: bool = enable_otlp

        self.registered_workers: list[BoostWorker] = []
        self.registered_cron_workers: list[BoostWorker] = []

        self.client_connector_args: ClientConnectorArgs = ClientConnectorArgs(
            temporal_endpoint=self.temporal_endpoint,
            temporal_namespace=self.temporal_namespace,
            enable_otlp=self.enable_otlp,
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

    def add_worker(
        self,
        worker_name: str,
        task_queue: str,
        workflows: list = [],
        activities: list = [],
        cron_schedule: str | None = None,
        cron_runner: typing.Coroutine | None = None
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
            name=worker_name,
            client_connector_args=self.client_connector_args,
            task_queue=task_queue,
            workflows=workflows,
            activities=activities,
            cron_schedule=cron_schedule,
            cron_runner=cron_runner
        )
        # Add this worker to `run` section in CLI
        self.run_typer.command(name=worker_name)(worker.run)

        if cron_schedule and cron_runner:
            # If cron_schedule and cron_runner is not None
            # register this worker as cron_worker too
            self.cron_typer.command(name=worker_name)(worker.cron)
            self.registered_cron_workers.append(worker)

        self.registered_workers.append(worker)

    def run(self):
        asyncio.run(self._root_typer())

    def register_all(self):

        # logger.warning('Use all-in-one mode only in dev mode!')
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
