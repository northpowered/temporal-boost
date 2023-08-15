# Base imports
import typer
import asyncio
# Local imports
from .worker import BoostWorker
from .schemas import ClientConnectorArgs


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

        self._root_typer.add_typer(self.run_typer, no_args_is_help=True)

    def add_worker(
        self,
        worker_name: str,
        task_queue: str,
        workflows: list = [],
        activities: list = [],
    ) -> None:
        worker: BoostWorker = BoostWorker(
            name=worker_name,
            client_connector_args=self.client_connector_args,
            task_queue=task_queue,
            workflows=workflows,
            activities=activities,
        )

        self.run_typer.command(name=worker_name)(worker.run)

        self.registered_workers.append(worker)

    def run(self):
        asyncio.run(self._root_typer())
