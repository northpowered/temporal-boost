"""Loop ownership and stop coordination shared by the built-in ASGI adapters."""

import asyncio
import signal
import threading
from abc import abstractmethod
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from importlib import import_module
from types import FrameType
from typing import Any

from temporal_boost.workers.base import BaseAsgiWorker


_active_worker: ContextVar[object | None] = ContextVar("active_asgi_worker", default=None)


def load_asgi_app(app: Any) -> Any:
    """Resolve module:attribute paths without evaluating arbitrary expressions.

    Raises:
        ValueError: If the import path is malformed.
        TypeError: If the resolved application is not callable.
    """
    if isinstance(app, str):
        module, separator, attribute = app.partition(":")
        if not separator or not module or not attribute:
            raise ValueError("ASGI application paths must use 'module:attribute'")
        app = import_module(module)
        for part in attribute.split("."):
            app = getattr(app, part)
    if not callable(app):
        raise TypeError("Expected an ASGI application callable or 'module:attribute' path")
    return app


async def capture_error(awaitable: Awaitable[None]) -> BaseException | None:
    """Keep fatal task exceptions from interrupting loop cleanup."""
    try:
        await awaitable
    except BaseException as exc:
        return exc
    return None


class ManagedAsgiWorker(BaseAsgiWorker):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._lock = threading.Lock()
        self._running = False
        self._completed = False
        self._stop_requested = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._owner: asyncio.Task[Any] | None = None
        self._server_task: asyncio.Task[BaseException | None] | None = None

    def request_stop(self) -> bool:
        with self._lock:
            if self._completed and not self._running:
                return True
            self._stop_requested = True
            if self._loop is not None and self._stop_event is not None:
                self._loop.call_soon_threadsafe(self._stop_event.set)
        return True

    def _handle_signal(self, _signum: int, _frame: FrameType | None) -> None:
        # A Python signal can interrupt the main thread while it holds _lock.
        self._stop_requested = True
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self.request_stop)

    def run(self) -> None:
        """Serve and join cleanup on a fresh loop; preserve all backend failures.

        Raises:
            RuntimeError: If this adapter is already running.
        """
        with self._lock:
            if self._running:
                raise RuntimeError(f"Worker '{self.name}' is already running")
            self._running = True
        handlers: dict[signal.Signals, Any] = {}
        try:
            if threading.current_thread() is threading.main_thread():
                for signum in (signal.SIGINT, signal.SIGTERM):
                    handlers[signum] = signal.signal(signum, self._handle_signal)
            error = asyncio.run(self._run_managed())
            if error is not None:
                raise error
        finally:
            for previous_signum, handler in handlers.items():
                signal.signal(previous_signum, handler)
            with self._lock:
                self._running = False
                self._completed = True
                self._stop_requested = False

    async def _run_managed(self) -> BaseException | None:
        stop = asyncio.Event()
        with self._lock:
            self._loop = asyncio.get_running_loop()
            self._owner = asyncio.current_task()
            self._stop_event = stop
            if self._stop_requested:
                stop.set()
        error: BaseException | None = None
        try:
            if stop.is_set():
                return None
            task = self._server_task = asyncio.create_task(self._run_backend(stop))
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError as exc:  # noqa: PERF203 - repeated cancellation still joins cleanup
                    if error is None:
                        error = exc
                    self.request_stop()
            result = task.result()
            return result if result is not None else error
        finally:
            with self._lock:
                self._loop = None
                self._stop_event = None
                self._owner = None
            self._server_task = None

    @abstractmethod
    async def _serve(self, stop: asyncio.Event) -> None:
        """Serve until the backend returns or stop is requested; own all cleanup."""

    async def _run_backend(self, stop: asyncio.Event) -> BaseException | None:
        token = _active_worker.set(self)
        try:
            return await capture_error(self._serve(stop))
        finally:
            _active_worker.reset(token)

    async def _serve_until_stopped(
        self, serve: Awaitable[None], stop: asyncio.Event, on_stop: Callable[[], Awaitable[None]]
    ) -> None:
        async def stopping() -> None:
            await stop.wait()
            await on_stop()

        serving = asyncio.create_task(capture_error(serve))
        stopper = asyncio.create_task(capture_error(stopping()))
        try:
            await asyncio.wait((serving, stopper), return_when=asyncio.FIRST_COMPLETED)
            if stopper.done() and (error := stopper.result()) is not None:
                serving.cancel()
                await serving
                raise error
            error = await serving
            if error is not None:
                raise error
        finally:
            stopper.cancel()
            await asyncio.gather(stopper, return_exceptions=True)

    async def shutdown(self) -> None:
        """Request stop and join the run on its owning loop; idle calls are safe.

        Raises:
            RuntimeError: If called from a foreign loop or the server's own task.
        """
        with self._lock:
            owner, loop = self._owner, self._loop
        if owner is None:
            return
        if asyncio.get_running_loop() is not loop:
            raise RuntimeError("Use request_stop() to stop an ASGI worker from another event loop")
        if _active_worker.get() is self or asyncio.current_task() in {owner, self._server_task}:
            raise RuntimeError("Use request_stop() from inside the ASGI worker lifecycle")
        self.request_stop()
        error = await asyncio.shield(owner)
        if error is not None:
            raise error
