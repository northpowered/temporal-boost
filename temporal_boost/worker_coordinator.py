import asyncio
import logging
import signal
import threading
import time
from concurrent.futures import CancelledError as FutureCancelledError
from queue import Empty, SimpleQueue
from types import FrameType
from typing import Any

from temporal_boost.workers.base import BaseBoostWorker


logger = logging.getLogger(__name__)


class WorkerCoordinator:
    """Run services until stop/failure and re-raise the first error after bounded cleanup."""

    def __init__(self, workers: list[BaseBoostWorker], shutdown_timeout: float) -> None:
        self._workers = workers
        self._shutdown_timeout = shutdown_timeout
        self._threads: list[tuple[BaseBoostWorker, threading.Thread]] = []
        self._stop_requested = False
        self._failures: SimpleQueue[tuple[str, BaseException]] = SimpleQueue()

    def request_stop(self) -> None:
        # A plain assignment also makes this safe to call from a signal handler:
        # no locks, worker callbacks, or logging run in that handler.
        self._stop_requested = True

    def is_alive(self) -> bool:
        return any(thread.is_alive() for _, thread in self._threads)

    def run(self) -> None:
        previous_handlers: dict[signal.Signals, Any] = {}
        try:
            if threading.current_thread() is threading.main_thread():
                for signum in (signal.SIGINT, signal.SIGTERM):
                    previous_handlers[signum] = signal.signal(signum, self._handle_signal)

            try:
                self._start_workers()
                while self.is_alive() and not self._stop_requested:
                    time.sleep(0.05)
            except BaseException as exc:
                self._record_failure("Worker startup or coordination", exc)
            finally:
                try:
                    self._stop_and_join()
                except BaseException as exc:
                    self._record_failure("Worker shutdown", exc)
            self._raise_first_failure()
        finally:
            for previous_signum, handler in previous_handlers.items():
                signal.signal(previous_signum, handler)

    def _handle_signal(self, _signum: int, _frame: FrameType | None) -> None:
        self.request_stop()

    def _start_workers(self) -> None:
        for worker in self._workers:
            if self._stop_requested:
                break
            thread = threading.Thread(
                target=self._run_worker, args=(worker,), name=f"worker-{worker.name}", daemon=True
            )
            thread.start()
            self._threads.append((worker, thread))
            logger.info("Started worker thread: %s", worker.name)

    def _run_worker(self, worker: BaseBoostWorker) -> None:
        try:
            worker.run()
        except BaseException as exc:
            if isinstance(exc, (asyncio.CancelledError, FutureCancelledError)) and self._stop_requested:
                return
            self._record_failure(f"Worker '{worker.name}'", exc)
        else:
            if not self._stop_requested:
                self._record_failure(
                    f"Worker '{worker.name}'",
                    RuntimeError(f"Worker '{worker.name}' returned before shutdown was requested"),
                )

    def _record_failure(self, source: str, error: BaseException) -> None:
        self._failures.put((source, error))
        self.request_stop()

    def _raise_first_failure(self) -> None:
        first_error: BaseException | None = None
        while True:
            try:
                source, error = self._failures.get_nowait()
            except Empty:
                break
            # This failure was captured in another thread; preserve its traceback.
            logger.error("%s failed", source, exc_info=(type(error), error, error.__traceback__))
            if first_error is None:
                first_error = error
        if first_error is not None:
            raise first_error

    def _stop_and_join(self) -> None:
        self.request_stop()
        deadline = time.monotonic() + self._shutdown_timeout
        for worker, thread in self._threads:
            if not thread.is_alive():
                continue
            try:
                if not worker.request_stop():
                    logger.warning("Worker '%s' does not support managed stopping", worker.name)
            except BaseException as exc:
                self._record_failure(f"Stop request for worker '{worker.name}'", exc)

        for _, thread in self._threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))

        pending = [worker.name for worker, thread in self._threads if thread.is_alive()]
        if pending:
            raise TimeoutError(f"Workers did not stop within {self._shutdown_timeout:g} seconds: {', '.join(pending)}")
