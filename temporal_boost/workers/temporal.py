import asyncio
import logging
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import CancelledError as FutureCancelledError
from typing import Any, Literal
from urllib.parse import quote

from temporalio.client import Client, WorkflowHandle
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.runtime import LoggingConfig, MetricBuffer, OpenTelemetryConfig, PrometheusConfig, Runtime
from temporalio.types import MethodAsyncNoParam
from temporalio.worker import Interceptor, Worker

from temporal_boost.temporal import config
from temporal_boost.temporal.client import TemporalClientBuilder
from temporal_boost.temporal.runtime import TemporalRuntimeBuilder
from temporal_boost.temporal.worker import TemporalWorkerBuilder
from temporal_boost.workers.base import BaseBoostWorker


logger = logging.getLogger(__name__)
_WorkerState = Literal["created", "building", "running", "stopping", "stopped"]


class TemporalBoostWorker(BaseBoostWorker):
    """Own one loop and one SDK worker per run, with a shared startup/stop lifecycle."""

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
        cron_workflow_id: str | None = None,
        debug_mode: bool = False,
        **worker_kwargs: Any,
    ) -> None:
        self.name = worker_name
        if cron_schedule is not None and not cron_schedule.strip():
            raise ValueError("cron_schedule must be a non-empty, non-whitespace string")
        if (cron_schedule is None) != (cron_runner is None):
            raise ValueError("cron_schedule and cron_runner must be provided together or both omitted")
        if cron_workflow_id is not None and not cron_workflow_id.strip():
            raise ValueError("cron_workflow_id must not be empty or whitespace-only")
        self._cron_workflow_id = (
            cron_workflow_id
            if cron_workflow_id is not None
            else f"temporal-boost/cron/{quote(task_queue, safe='')}/{quote(worker_name, safe='')}"
        )
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

        self._runtime_builder: TemporalRuntimeBuilder | None = None
        self._runtime: Runtime | None = None

        self._cron_future: asyncio.Future[Any] | None = None
        self._lifecycle_lock = threading.Lock()
        self._initializing_resources = False
        self._state: _WorkerState = "created"
        self._loop: asyncio.AbstractEventLoop | None = None
        self._owner_task: asyncio.Task[Any] | None = None
        self._stop_event: asyncio.Event | None = None
        self._stop_requested = False
        self._build_task: asyncio.Task[None] | None = None
        self._sdk_task: asyncio.Task[None] | None = None
        self._cron_task: asyncio.Task[None] | None = None

    @property
    def state(self) -> _WorkerState:
        return self._state

    def request_stop(self) -> bool:
        with self._lifecycle_lock:
            if self._state == "stopped":
                return True
            self._stop_requested = True
            if self._loop is not None and self._stop_event is not None:
                self._loop.call_soon_threadsafe(self._stop_event.set)
        return True

    @property
    def cron_workflow_id(self) -> str:
        """Stable CRON workflow identity within the configured Temporal namespace."""
        return self._cron_workflow_id

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
        if self._cron_runner is None:
            raise RuntimeError("Cron runner is not configured. Provide a valid cron_runner.")
        return self._cron_runner

    def _require_cron_configuration(self) -> None:
        if not self._cron_schedule.strip() or self._cron_runner is None:
            raise RuntimeError("CRON execution requires both cron_schedule and cron_runner")

    @property
    def temporal_client_runtime(self) -> Runtime:
        """Create/cache the runtime, freezing its configuration until run cleanup.

        Raises:
            RuntimeError: If cleanup is in progress and no runtime remains.
        """
        with self._lifecycle_lock:
            if self._runtime is None:
                if self._state == "stopping":
                    raise RuntimeError("Cannot initialize a Temporal runtime during cleanup")
                if self._runtime_builder is None:
                    self._runtime_builder = TemporalRuntimeBuilder()
                self._runtime = self._runtime_builder.build()
            return self._runtime

    def _require_configurable(self, component: Literal["client", "runtime"]) -> None:
        # The caller holds _lifecycle_lock, including during builder mutations.
        initialized = self._client is not None or self._worker is not None
        if (
            self._state in {"building", "running", "stopping"}
            or self._initializing_resources
            or initialized
            or (component == "runtime" and self._runtime is not None)
        ):
            raise RuntimeError(
                f"Cannot configure Temporal {component} after initialization or during a run. "
                "Configure before initialization or after the run has finished cleanup."
            )

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
        """Update future connection options before initialization or after cleanup."""
        with self._lifecycle_lock:
            self._require_configurable("client")
            if self._client_builder is None:
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
                self._client_builder.set_tls(tls)

            if use_pydantic_data_converter is not None:
                self._client_builder.set_pydantic_data_converter(enabled=use_pydantic_data_converter)

            if kwargs:
                self._client_builder.set_kwargs(**kwargs)

    def configure_temporal_runtime(  # noqa: PLR0913
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
        """Replace runtime options before first runtime creation or after cleanup."""
        with self._lifecycle_lock:
            self._require_configurable("runtime")
            self._runtime_builder = TemporalRuntimeBuilder(
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
        with self._lifecycle_lock:
            if self._initializing_resources or self._client is not None or self._worker is not None:
                raise RuntimeError("Temporal worker resources are already initialized or initializing")
            self._initializing_resources = True
        try:
            if self._client_builder is None:
                self._client_builder = TemporalClientBuilder()
            self._client_builder.set_runtime(self.temporal_client_runtime)
            self._client = await self._client_builder.build()

            self._worker_builder.set_client(self._client)
            self._worker = self._worker_builder.build()
        finally:
            with self._lifecycle_lock:
                self._initializing_resources = False

    async def _run_worker(self) -> None:
        await self._run_lifecycle(with_cron=False)

    async def _register_cron(self) -> WorkflowHandle[Any, Any]:
        """Atomically start or reuse an active CRON chain; reject a closed ID."""
        self._require_cron_configuration()
        handle = await self.temporal_client.start_workflow(
            self.temporal_cron_runner,
            id=self.cron_workflow_id,
            task_queue=self._worker_builder.task_queue,
            cron_schedule=self._cron_schedule,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
        logger.info(
            "CRON workflow registered or already running: worker=%s namespace=%s workflow_id=%s run_id=%s",
            self.name,
            self.temporal_client.namespace,
            handle.id,
            handle.result_run_id,
        )
        return handle

    async def _run_with_cron(self) -> None:
        self._require_cron_configuration()
        await self._run_lifecycle(with_cron=True)

    async def _run_lifecycle(self, *, with_cron: bool) -> None:
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()
        with self._lifecycle_lock:
            if self._owner_task is not None:
                raise RuntimeError(f"Worker '{self.name}' is already running")
            self._owner_task = asyncio.current_task()
            self._loop = loop
            self._stop_event = stop_event
            self._state = "building"
            if self._stop_requested:
                stop_event.set()

        stop_task = asyncio.create_task(stop_event.wait())
        error: BaseException | None = None
        try:
            if not stop_event.is_set():
                await self._serve(stop_task, with_cron=with_cron)
        except BaseException as exc:
            error = exc
        finally:
            try:
                error = await self._finish_cleanup(error)
            finally:
                stop_task.cancel()
                try:
                    await asyncio.gather(stop_task, return_exceptions=True)
                finally:
                    self._release_resources()
        if error is not None:
            raise error

    async def _serve(self, stop_task: asyncio.Task[bool], *, with_cron: bool) -> None:
        self._build_task = asyncio.create_task(self._build_worker())
        await asyncio.wait((self._build_task, stop_task), return_when=asyncio.FIRST_COMPLETED)
        if self._build_task.done():
            await self._build_task
        if self._stop_requested:
            return

        self._log_worker_start()
        self._state = "running"
        self._sdk_task = asyncio.create_task(self.temporal_worker.run())
        tasks: list[asyncio.Task[Any]] = [self._sdk_task, stop_task]
        if with_cron:
            self._cron_future = asyncio.get_running_loop().create_future()
            self._cron_task = asyncio.create_task(self._register_cron_and_wait())
            tasks.append(self._cron_task)
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in (self._sdk_task, self._cron_task):
            if task is not None and task.done():
                await task

    async def _register_cron_and_wait(self) -> None:
        await self._register_cron()
        if self._cron_future is not None:
            await self._cron_future

    async def _finish_cleanup(self, error: BaseException | None) -> BaseException | None:
        self._state = "stopping"
        cleanup_task = asyncio.create_task(self._cleanup(error))
        while not cleanup_task.done():
            try:
                await asyncio.shield(cleanup_task)
            except asyncio.CancelledError as exc:  # noqa: PERF203 - repeated cancellation must still wait for cleanup
                # Cancelling a waiter must not abandon resources on the owning loop.
                if error is None:
                    error = exc
            except BaseException:
                break
        try:
            cleanup_task.result()
        except BaseException as exc:
            if error is None or isinstance(error, (asyncio.CancelledError, FutureCancelledError)):
                error = exc
            else:
                logger.exception("Cleanup failed for worker '%s'; preserving lifecycle error", self.name)
        return error

    async def _cleanup(self, primary: BaseException | None) -> None:
        errors: list[BaseException] = []
        if self._cron_future is not None and not self._cron_future.done():
            self._cron_future.set_result(None)
        for task in (self._build_task, self._cron_task):
            if task is None:
                continue
            task.cancel()
            result = (await asyncio.gather(task, return_exceptions=True))[0]
            if (
                isinstance(result, BaseException)
                and not isinstance(result, asyncio.CancelledError)
                and result is not primary
            ):
                errors.append(result)
        try:
            await self._stop_sdk_worker()
        except BaseException as exc:
            if exc is not primary:
                errors.append(exc)
        for error in errors[1:]:
            logger.error("Additional cleanup failure for worker '%s'", self.name, exc_info=error)
        if errors:
            raise errors[0]

    async def _stop_sdk_worker(self) -> None:
        if self._sdk_task is None:
            return
        if self._sdk_task.done():
            await self._sdk_task
            return
        shutdown_task = asyncio.create_task(self.temporal_worker.shutdown())
        failure: BaseException | None = None
        try:
            await asyncio.wait((self._sdk_task, shutdown_task), return_when=asyncio.FIRST_COMPLETED)
            # run() may fail validation without ever completing SDK shutdown().
            if self._sdk_task.done():
                await self._sdk_task
                if not shutdown_task.done():
                    return
            await shutdown_task
            await self._sdk_task
        except BaseException as exc:
            failure = exc
            raise
        finally:
            shutdown_task.cancel()
            self._sdk_task.cancel()
            results = await asyncio.gather(shutdown_task, self._sdk_task, return_exceptions=True)
            for result in results:
                if (
                    isinstance(result, BaseException)
                    and not isinstance(result, asyncio.CancelledError)
                    and result is not failure
                ):
                    logger.error("Additional SDK cleanup failure for worker '%s'", self.name, exc_info=result)

    def _release_resources(self) -> None:
        self._worker_builder.set_client(None)
        if self._client_builder is not None:
            self._client_builder.set_runtime(None)
        self._worker = None
        self._client = None
        self._runtime = None
        self._cron_future = None
        self._build_task = None
        self._sdk_task = None
        self._cron_task = None
        with self._lifecycle_lock:
            self._loop = None
            self._owner_task = None
            self._stop_event = None
            self._stop_requested = False
            self._state = "stopped"

    def run(self) -> None:
        """Consume the task queue without registering a CRON workflow."""
        try:
            asyncio.run(self._run_worker())
        except Exception:
            logger.exception(f"Worker {self.name} failed")
            raise

    async def shutdown(self) -> None:
        with self._lifecycle_lock:
            owner = self._owner_task
            owner_loop = self._loop
        if owner is None:
            return
        if asyncio.get_running_loop() is not owner_loop:
            raise RuntimeError("Use request_stop() to stop a Temporal worker from another event loop")
        if asyncio.current_task() in {owner, self._build_task, self._sdk_task, self._cron_task}:
            raise RuntimeError("Use request_stop() from inside the Temporal worker lifecycle")
        self.request_stop()
        await asyncio.shield(owner)

    def cron(self) -> None:
        """Register or reuse the CRON workflow and consume its task queue."""
        self._require_cron_configuration()
        logger.info(
            f"Cron worker {self.name} started on {self._worker_builder.task_queue} queue "
            f"with schedule {self._cron_schedule}",
        )
        try:
            asyncio.run(self._run_with_cron())
        except Exception:
            logger.exception(f"Cron worker {self.name} failed")
            raise

    def _log_worker_start(self) -> None:
        activity_names = [f"{act.__name__}" for act in self._worker_builder._activities]  # noqa: SLF001
        workflow_names = [f"{wf.__name__}" for wf in self._worker_builder._workflows]  # noqa: SLF001

        logger.info(
            f"Worker '{self.name}' started on task queue '{self._worker_builder.task_queue}' with "
            f"workflows: {workflow_names} and activities: {activity_names}",
        )
