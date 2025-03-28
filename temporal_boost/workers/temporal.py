import asyncio
import logging
import uuid
from collections.abc import Callable, Mapping
from typing import Any, cast

from temporalio.client import Client
from temporalio.runtime import (
    LoggingConfig,
    MetricBuffer,
    OpenTelemetryConfig,
    PrometheusConfig,
    Runtime,
)
from temporalio.types import MethodAsyncNoParam
from temporalio.worker import Worker
from temporalio.worker._interceptor import Interceptor

from temporal_boost.temporal import config
from temporal_boost.temporal.client import TemporalClientBuilder
from temporal_boost.temporal.runtime import create_runtime
from temporal_boost.temporal.worker import TemporalWorkerBuilder
from temporal_boost.workers.base import BaseBoostWorker


logger = logging.getLogger(__name__)


class TemporalBoostWorker(BaseBoostWorker):
    def __init__(  # noqa: PLR0913
        self,
        worker_name: str,
        task_queue: str,
        *,
        activities: list[Callable[..., Any]] | None = None,
        workflows: list[type] | None = None,
        interceptors: list[Interceptor] | None = None,
        cron_schedule: str | None = None,
        cron_runner: MethodAsyncNoParam[Any, Any] | None = None,
        debug_mode: bool = False,
        **worker_kwargs: Any,
    ) -> None:
        self.name = worker_name
        activities = activities or []
        workflows = workflows or []
        interceptors = interceptors or []

        if not workflows and not activities:
            raise RuntimeError("BoostWorker must have at least one workflow or activity defined")

        self._worker_builder = TemporalWorkerBuilder(
            task_queue=task_queue,
            debug_mode=debug_mode,
            **worker_kwargs,
        )
        self._worker_builder.set_activities(activities)
        self._worker_builder.set_workflows(workflows)
        self._worker_builder.set_interceptors(interceptors)
        self._worker: Worker | None = None

        self._cron_schedule = cron_schedule or ""
        self._cron_runner = cron_runner

        self._client_builder: TemporalClientBuilder | None = None
        self._client: Client | None = None

        self._runtime: Runtime | None = None

    @property
    def temporal_client(self) -> Client:
        if not self._client:
            raise RuntimeError(
                "Temporal client has not been initialized. Ensure 'configure_temporal_client()' has been called"
            )
        return self._client

    @property
    def temporal_worker(self) -> Worker:
        if not self._worker:
            raise RuntimeError("Temporal worker has not been initialized. Ensure _build_worker() has been called")
        return self._worker

    @property
    def temporal_cron_runner(self) -> MethodAsyncNoParam[Any, Any]:
        if not self._cron_runner:
            raise RuntimeError("Cron runner is not configured. Provide a valid cron_runner.")
        return self._cron_runner

    @property
    def temporal_client_runtime(self) -> Runtime:
        if not self._runtime:
            self.configur_temporal_runtime()
        return cast("Runtime", self._runtime)

    def configure_temporal_client(  # noqa: PLR0913
        self,
        *,
        target_host: str | None = None,
        namespace: str | None = None,
        api_key: str | None = None,
        identity: str | None = None,
        tls: bool | None = None,
        use_pydantic_data_converter: bool | None = None,
        **kwargs: Any,
    ) -> None:
        if not self._client_builder:
            self._client_builder = TemporalClientBuilder(
                target_host=target_host or config.TARGET_HOST,
                namespace=namespace,
                api_key=api_key,
                identity=identity,
                tls=tls,
                use_pydantic_data_converter=use_pydantic_data_converter,
                **kwargs,
            )

        if target_host is not None:
            self._client_builder.set_target_host(target_host)

        if namespace is not None:
            self._client_builder.set_namespace(namespace)

        if api_key is not None:
            self._client_builder.set_api_key(api_key)

        if identity is not None:
            self._client_builder.set_identity(identity)

        if tls is not None:
            self._client_builder.set_tls_connent(tls)

        if use_pydantic_data_converter is not None:
            self._client_builder.set_pydantic_data_converter()

        self._client_builder.set_runtime(self.temporal_client_runtime)

    def configur_temporal_runtime(  # noqa: PLR0913
        self,
        *,
        logging: LoggingConfig | None = None,
        metrics: OpenTelemetryConfig | PrometheusConfig | MetricBuffer | None = None,
        global_tags: Mapping[str, str] | None = None,
        attach_service_name: bool = True,
        metric_prefix: str | None = None,
        prometheus_bind_address: str | None = config.PROMETHEUS_BIND_ADDRESS,
        prometheus_counters_total_suffix: bool | None = config.PROMETHEUS_COUNTERS_TOTAL_SUFFIX,
        prometheus_unit_suffix: bool | None = config.PROMETHEUS_UNIT_SUFFIX,
        prometheus_durations_as_seconds: bool | None = config.PROMETHEUS_DURATIONS_AS_SECONDS,
    ) -> None:
        self._runtime = create_runtime(
            logging=logging,
            metrics=metrics,
            global_tags=global_tags,
            attach_service_name=attach_service_name,
            metric_prefix=metric_prefix,
            prometheus_bind_address=prometheus_bind_address,
            prometheus_counters_total_suffix=prometheus_counters_total_suffix,
            prometheus_unit_suffix=prometheus_unit_suffix,
            prometheus_durations_as_seconds=prometheus_durations_as_seconds,
        )

    async def _build_worker(self) -> None:
        if not self._client_builder:
            self.configure_temporal_client()
            self._client_builder = cast("TemporalClientBuilder", self._client_builder)

        self._client = await self._client_builder.build()
        self._worker_builder.set_client(self._client)
        self._worker = self._worker_builder.build()

    async def _run_worker(self) -> None:
        await self._build_worker()
        await self.temporal_worker.run()

    async def _run_with_cron(self) -> None:
        await self._build_worker()
        async with self.temporal_worker:
            workflow_id = str(uuid.uuid4())
            await self.temporal_client.start_workflow(
                self.temporal_cron_runner,
                id=workflow_id,
                task_queue=self._worker_builder.task_queue,
                cron_schedule=self._cron_schedule,
            )
            await asyncio.Future()

    def run(self) -> None:
        logger.info(f"Worker {self.name} started on {self._worker_builder.task_queue} queue")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._run_worker())

    async def shutdown(self) -> None:
        await self.temporal_worker.shutdown()

    def cron(self) -> None:
        logger.info(
            f"Cron worker {self.name} started on {self._worker_builder.task_queue} queue "
            f"with schedule {self._cron_schedule}"
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._run_with_cron())
