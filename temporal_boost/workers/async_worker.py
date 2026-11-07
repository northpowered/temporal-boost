import asyncio
import logging
import threading
from abc import abstractmethod
from concurrent.futures import CancelledError as FutureCancelledError

from temporal_boost.workers.base import BaseBoostWorker


logger = logging.getLogger(__name__)


class AsyncBoostWorker(BaseBoostWorker):
    """Opt-in lifecycle for workers owning an asyncio loop in their run thread.

    Subclasses call super().__init__(), implement run_async() and shutdown(), and
    leave run() unchanged. shutdown() must safely handle partial startup and make
    run_async() return. It runs once per run(), on the same loop as run_async().
    """

    def __init__(self) -> None:
        self._lifecycle_lock = threading.Lock()
        self._running = False
        self._stop_requested = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None

    @abstractmethod
    async def run_async(self) -> None:
        """Initialize resources and serve until shutdown() requests completion."""

    def request_stop(self) -> bool:
        with self._lifecycle_lock:
            self._stop_requested = True
            if self._loop is not None and self._stop_event is not None:
                self._loop.call_soon_threadsafe(self._stop_event.set)
        return True

    def run(self) -> None:
        with self._lifecycle_lock:
            if self._running:
                raise RuntimeError(f"Worker '{self.name}' is already running")
            self._running = True
        try:
            asyncio.run(self._run_managed())
        finally:
            with self._lifecycle_lock:
                self._running = False
                self._stop_requested = False

    async def _run_managed(self) -> None:
        stop_event = asyncio.Event()
        with self._lifecycle_lock:
            self._loop = asyncio.get_running_loop()
            self._stop_event = stop_event
            if self._stop_requested:
                stop_event.set()

        run_task = asyncio.create_task(self.run_async())
        stop_task = asyncio.create_task(stop_event.wait())
        try:
            try:
                await asyncio.wait((run_task, stop_task), return_when=asyncio.FIRST_COMPLETED)
                if run_task.done():
                    run_task.result()
            except BaseException as run_error:
                try:
                    await self.shutdown()
                except BaseException:
                    if isinstance(run_error, (asyncio.CancelledError, FutureCancelledError)):
                        raise
                    logger.exception("Cleanup failed for worker '%s'; preserving run error", self.name)
                raise
            else:
                await self.shutdown()
            await run_task
        finally:
            with self._lifecycle_lock:
                self._loop = None
                self._stop_event = None
            run_task.cancel()
            stop_task.cancel()
            await asyncio.gather(run_task, stop_task, return_exceptions=True)
