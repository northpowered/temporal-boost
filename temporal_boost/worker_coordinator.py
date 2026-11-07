import logging
import signal
import threading
import time
from types import FrameType
from typing import Any

from temporal_boost.workers.base import BaseBoostWorker


logger = logging.getLogger(__name__)


class WorkerCoordinator:
    """Own worker threads and bound their cooperative shutdown by one deadline."""

    def __init__(self, workers: list[BaseBoostWorker], shutdown_timeout: float) -> None:
        self._workers = workers
        self._shutdown_timeout = shutdown_timeout
        self._threads: list[tuple[BaseBoostWorker, threading.Thread]] = []
        self._stop_requested = False

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
            finally:
                self._stop_and_join()
        finally:
            for previous_signum, handler in previous_handlers.items():
                signal.signal(previous_signum, handler)

    def _handle_signal(self, _signum: int, _frame: FrameType | None) -> None:
        self.request_stop()

    def _start_workers(self) -> None:
        for worker in self._workers:
            if self._stop_requested:
                break
            thread = threading.Thread(target=worker.run, name=f"worker-{worker.name}", daemon=True)
            thread.start()
            self._threads.append((worker, thread))
            logger.info("Started worker thread: %s", worker.name)

    def _stop_and_join(self) -> None:
        self.request_stop()
        deadline = time.monotonic() + self._shutdown_timeout
        for worker, thread in self._threads:
            if not thread.is_alive():
                continue
            try:
                if not worker.request_stop():
                    logger.warning("Worker '%s' does not support managed stopping", worker.name)
            except Exception:
                logger.exception("Stop request failed for worker '%s'", worker.name)

        for _, thread in self._threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))

        pending = [worker.name for worker, thread in self._threads if thread.is_alive()]
        if pending:
            raise TimeoutError(f"Workers did not stop within {self._shutdown_timeout:g} seconds: {', '.join(pending)}")
