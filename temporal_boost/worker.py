# Base imports
import asyncio
import uuid
import typing
# Temporal SDK imports
from temporalio.worker import Worker
from temporalio.client import Client
from temporalio import workflow
# Local imports
from .schemas import ClientConnectorArgs
from .connect import create_temporal_client_connector

# Avoid circular import for type hints
if typing.TYPE_CHECKING:
    from . import BoostApp


class BoostWorker:
    def __init__(
        self,
        app: "BoostApp",
        name: str,
        client_connector_args: ClientConnectorArgs,
        task_queue: str,
        activities: list = [],
        workflows: list = [],
        cron_schedule: str | None = None,
        cron_runner: typing.Coroutine | None = None,
        metrics_endpoint: str | None = None
    ) -> None:

        self.app: "BoostApp" = app
        self.name: str = name
        self.client_connector_args: ClientConnectorArgs = client_connector_args
        self.task_queue: str = task_queue
        self.activities: list = activities
        self.workflows: list = workflows
        self.cron_schedule: str | None = cron_schedule
        self.cron_runner: workflow.run | None = cron_runner
        self.metrics_endpoint: str | None = metrics_endpoint

    async def _run_worker(self):
        client: Client = await create_temporal_client_connector(
            app=self.app,
            temporal_endpoint=self.client_connector_args.temporal_endpoint,
            temporal_namespace=self.client_connector_args.temporal_namespace,
            metrics_endpoint=self.metrics_endpoint
        )
        if not client:
            return

        worker: Worker = Worker(
            client=client,
            task_queue=self.task_queue,
            activities=self.activities,
            workflows=self.workflows,
        )
        await worker.run()

    async def _run_with_cron(self):

        client: Client = await create_temporal_client_connector(
            app=self.app,
            temporal_endpoint=self.client_connector_args.temporal_endpoint,
            temporal_namespace=self.client_connector_args.temporal_namespace,
        )
        if not client:
            return

        async with Worker(
            client=client,
            task_queue=self.task_queue,
            activities=self.activities,
            workflows=self.workflows,
        ):
            workflow_id: str = str(uuid.uuid4())
            await client.start_workflow(
                self.cron_runner,
                id=workflow_id,
                task_queue=self.task_queue,
                cron_schedule=self.cron_schedule
            )
            await asyncio.Future()

    def run(self):
        self.app.logger.info(f"Worker {self.name} started on {self.task_queue} queue")
        asyncio.run(self._run_worker())
        return self.name

    def cron(self):
        self.app.logger.info(f"Cron worker {self.name} started on {self.task_queue} queue with schedule {self.cron_schedule}")
        asyncio.run(self._run_with_cron())
        return self.name
