# Base imports
import asyncio
import typing
import uuid

# Temporal SDK imports
from temporalio.worker import Worker

from .connect import create_temporal_client_connector

# Local imports
from .schemas import ClientConnectorArgs, WorkerType

# Avoid circular import for type hints
if typing.TYPE_CHECKING:
    from temporalio import workflow
    from temporalio.client import Client

    from . import BoostApp


class BoostWorker:
    def __init__(  # noqa: PLR0913, PLR0917
        self,
        app: "BoostApp",
        name: str,
        client_connector_args: ClientConnectorArgs,
        task_queue: str,
        activities: list | None = None,
        workflows: list | None = None,
        cron_schedule: str | None = None,
        cron_runner: typing.Coroutine | None = None,
        metrics_endpoint: str | None = None,
        description: str = "",
        **worker_kwargs: typing.Any,
    ) -> None:
        if workflows is None:
            workflows = []
        if activities is None:
            activities = []
        self.app: BoostApp = app
        self.name: str = name
        self.client_connector_args: ClientConnectorArgs = client_connector_args
        self.task_queue: str = task_queue
        self.activities: list = activities
        self.workflows: list = workflows
        self.cron_schedule: str | None = cron_schedule
        self.cron_runner: workflow.run | None = cron_runner
        self.metrics_endpoint: str | None = metrics_endpoint
        self.description: str = description
        self.type: WorkerType = WorkerType.TEMPORAL
        self._worker_kwargs = worker_kwargs

    async def _run_worker(self) -> None:
        client: Client = await create_temporal_client_connector(
            app=self.app,
            temporal_endpoint=self.client_connector_args.temporal_endpoint,
            temporal_namespace=self.client_connector_args.temporal_namespace,
            metrics_endpoint=self.metrics_endpoint,
        )
        if not client:
            return

        worker: Worker = Worker(
            client=client,
            task_queue=self.task_queue,
            activities=self.activities,
            workflows=self.workflows,
            **self._worker_kwargs,
        )
        await worker.run()

    async def _run_with_cron(self) -> None:
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
            **self._worker_kwargs,
        ):
            workflow_id: str = str(uuid.uuid4())
            await client.start_workflow(self.cron_runner, id=workflow_id, task_queue=self.task_queue, cron_schedule=self.cron_schedule)
            await asyncio.Future()

    def run(self) -> str:
        self.app.logger.info(f"Worker {self.name} started on {self.task_queue} queue")
        asyncio.run(self._run_worker())
        return self.name

    def cron(self) -> str:
        self.app.logger.info(f"Cron worker {self.name} started on {self.task_queue} queue with schedule {self.cron_schedule}")
        asyncio.run(self._run_with_cron())
        return self.name
