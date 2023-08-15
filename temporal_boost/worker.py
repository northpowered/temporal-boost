# Base imports
import asyncio
# Temporal SDK imports
from temporalio.worker import Worker
from temporalio.client import Client
# Local imports
from .schemas import ClientConnectorArgs
from .connect import create_temporal_client_connector


class BoostWorker:
    def __init__(
        self,
        name: str,
        client_connector_args: ClientConnectorArgs,
        task_queue: str,
        activities: list = [],
        workflows: list = [],
    ) -> None:
        self.name: str = name
        self.client_connector_args: ClientConnectorArgs = client_connector_args
        self.task_queue: str = task_queue
        self.activities: list = activities
        self.workflows: list = workflows

    async def _run_worker(self):
        client: Client = await create_temporal_client_connector(
            temporal_endpoint=self.client_connector_args.temporal_endpoint,
            temporal_namespace=self.client_connector_args.temporal_namespace,
            enable_otlp=self.client_connector_args.enable_otlp,
        )
        worker: Worker = Worker(
            client=client,
            task_queue=self.task_queue,
            activities=self.activities,
            workflows=self.workflows,
        )
        await worker.run()

    def run(self):
        print(f"This is worker {self.name}")
        asyncio.run(self._run_worker())

        return self.name
