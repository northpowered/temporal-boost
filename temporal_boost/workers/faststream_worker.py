import asyncio
import logging
import signal
import threading
from concurrent.futures import CancelledError as FutureCancelledError
from types import FrameType
from typing import Any

from temporal_boost.workers.base import BaseBoostWorker


logger = logging.getLogger(__name__)


class FastStreamBoostWorker(BaseBoostWorker):
    """Own FastStream startup, broker stop, and lifespan in one asyncio loop."""

    def __init__(
        self,
        app: Any,
        *,
        log_level: str | int | None = None,
        **faststream_kwargs: Any,
    ) -> None:
        self.name = "faststream"
        self._app = app
        self._log_level = logging.INFO if log_level is None else log_level
        self._faststream_kwargs = faststream_kwargs
        self._lock = threading.Lock()
        self._running = False
        self._completed = False
        self._stop_requested = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._owner_task: asyncio.Task[Any] | None = None
        self._lifecycle_task: asyncio.Task[BaseException | None] | None = None
        self._startup_task: asyncio.Task[BaseException | None] | None = None

    def request_stop(self) -> bool:
        with self._lock:
            if self._completed and not self._running and self._loop is None:
                return True
            self._stop_requested = True
            if self._loop is not None and self._stop_event is not None:
                self._loop.call_soon_threadsafe(self._stop_event.set)
        return True

    def _handle_signal(self, _signum: int, _frame: FrameType | None) -> None:
        # The signal handler must not acquire the lifecycle lock.
        self._stop_requested = True
        if self._loop is not None:
            # Wake the selector as well as queueing the stop request.
            self._loop.call_soon_threadsafe(self.request_stop)

    def run(self) -> None:
        """Run until request_stop(), preserving startup and cleanup failures.

        Raises:
            RuntimeError: If already running or the optional dependency is missing.
            TypeError: If app is not a FastStream instance.
        """
        with self._lock:
            if self._running:
                raise RuntimeError(f"Worker '{self.name}' is already running")
            self._running = True
        previous_handlers: dict[signal.Signals, Any] = {}
        try:
            try:
                import anyio  # noqa: PLC0415
                from faststream import FastStream  # noqa: PLC0415
            except ImportError as exc:
                raise RuntimeError("faststream is not installed. Install temporal-boost[faststream].") from exc
            if not isinstance(self._app, FastStream):
                raise TypeError(f"Expected FastStream instance, got {type(self._app)}")
            logging.getLogger("faststream").setLevel(self._log_level)
            if threading.current_thread() is threading.main_thread():
                for signum in (signal.SIGINT, signal.SIGTERM):
                    previous_handlers[signum] = signal.signal(signum, self._handle_signal)
            logger.info("Starting FastStream worker '%s'", self.name)
            error = anyio.run(self._run_managed, backend="asyncio")
            # Raise fatal BaseExceptions only after AnyIO has closed the loop.
            if error is not None:
                raise error
        finally:
            for previous_signum, handler in previous_handlers.items():
                signal.signal(previous_signum, handler)
            with self._lock:
                self._running = False
                self._completed = True
                self._stop_requested = False

    async def _run_managed(self) -> BaseException | None:
        stop = asyncio.Event()
        with self._lock:
            self._loop = asyncio.get_running_loop()
            self._owner_task = asyncio.current_task()
            self._stop_event = stop
            if self._stop_requested:
                stop.set()
        error: BaseException | None = None
        try:
            if stop.is_set():
                return None
            task = self._lifecycle_task = asyncio.create_task(self._run_lifecycle(stop))
            # A lifespan can contain task-bound AnyIO cancel scopes. Enter/exit
            # it in one task, shielded from cancellation of the outer waiter.
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError as exc:  # noqa: PERF203 - repeated cancellation must still join cleanup
                    if error is None:
                        error = exc
                    self.request_stop()
            result = task.result()
            return result if result is not None else error
        finally:
            with self._lock:
                self._loop = None
                self._owner_task = None
                self._stop_event = None
            self._lifecycle_task = None
            self._startup_task = None

    def _cleanup_error(self, primary: BaseException | None, error: BaseException) -> BaseException:
        if primary is None or isinstance(primary, (asyncio.CancelledError, FutureCancelledError)):
            return error
        if error is not primary:
            # Cleanup errors can be logged after their exception handler has exited.
            logger.error(
                "Cleanup failed for FastStream worker '%s'; preserving lifecycle error",
                self.name,
                exc_info=error,
            )
        return primary

    async def _run_lifecycle(self, stop: asyncio.Event) -> BaseException | None:
        error: BaseException | None = None
        try:
            async with self._app.lifespan_context(**self._faststream_kwargs):
                try:
                    await self._start_and_wait(stop)
                except BaseException as exc:
                    error = exc
                error = await self._stop_application(error)
                if error is not None:
                    raise error
        except BaseException as exc:
            error = self._cleanup_error(error, exc)
        if error is None:
            logger.info("FastStream worker '%s' shutdown completed", self.name)
        return error

    async def _stop_application(self, error: BaseException | None) -> BaseException | None:
        import anyio  # noqa: PLC0415

        # A failed lifespan task can cancel its AnyIO scope. Cleanup
        # must still be able to reach broker cancellation checkpoints.
        with anyio.CancelScope(shield=True):
            try:
                await self._app.stop()
            except BaseException as exc:
                error = self._cleanup_error(error, exc)
                # A failing on_shutdown hook can prevent FastStream.stop()
                # from reaching the broker. Its public stop is idempotent.
                if self._app.broker is not None:
                    try:
                        await self._app.broker.stop()
                    except BaseException as broker_error:
                        error = self._cleanup_error(error, broker_error)
        return error

    async def _start_application(self) -> BaseException | None:
        try:
            await self._app.start(**self._faststream_kwargs)
            if self._app.broker is None:
                raise RuntimeError("FastStream application has no broker after startup")
        except BaseException as exc:
            return exc
        return None

    async def _start_and_wait(self, stop: asyncio.Event) -> None:
        import anyio  # noqa: PLC0415

        startup = self._startup_task = asyncio.create_task(self._start_application())
        stopping = asyncio.create_task(stop.wait())
        try:
            await asyncio.wait((startup, stopping), return_when=asyncio.FIRST_COMPLETED)
            if startup.done():
                error = startup.result()
                if error is not None:
                    raise error
            await stopping
        finally:
            startup.cancel()
            stopping.cancel()
            with anyio.CancelScope(shield=True):
                result, _ = await asyncio.gather(startup, stopping, return_exceptions=True)
            if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                raise result

    async def shutdown(self) -> None:
        """Request stop and wait on the owning loop; idle calls are harmless.

        Raises:
            RuntimeError: If called from a foreign loop or a lifecycle callback.
        """
        with self._lock:
            owner, loop = self._owner_task, self._loop
        if owner is None:
            return
        if asyncio.get_running_loop() is not loop:
            raise RuntimeError("Use request_stop() to stop a FastStream worker from another event loop")
        if asyncio.current_task() in {owner, self._lifecycle_task, self._startup_task}:
            raise RuntimeError("Use request_stop() from inside the FastStream worker lifecycle")
        self.request_stop()
        error = await asyncio.shield(owner)
        if error is not None:
            raise error
