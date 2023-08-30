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


class BoostWorker:
    def __init__(
        self,
        name: str,
        client_connector_args: ClientConnectorArgs,
        task_queue: str,
        activities: list = [],
        workflows: list = [],
        cron_schedule: str | None = None,
        cron_runner: typing.Coroutine | None = None
    ) -> None:
        self.name: str = name
        self.client_connector_args: ClientConnectorArgs = client_connector_args
        self.task_queue: str = task_queue
        self.activities: list = activities
        self.workflows: list = workflows
        self.cron_schedule: str | None = cron_schedule
        self.cron_runner: workflow.run | None = cron_runner

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
            workflows=self.workflows
        )
        await worker.run()

    async def _run_with_cron(self):

        client: Client = await create_temporal_client_connector(
            temporal_endpoint=self.client_connector_args.temporal_endpoint,
            temporal_namespace=self.client_connector_args.temporal_namespace,
            enable_otlp=self.client_connector_args.enable_otlp,
        )

        async with Worker(
            client=client,
            task_queue=self.task_queue,
            activities=self.activities,
            workflows=self.workflows
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
        print(f"This is worker {self.name}")  # do not forget to delete!
        asyncio.run(self._run_worker())
        return self.name

    def cron(self,):
        asyncio.run(self._run_with_cron())
        return self.name
