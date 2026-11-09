import logging
import math
import signal
import threading
import time
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from types import FrameType
from typing import Any

from temporal_boost.cli.importer import import_app_object
from temporal_boost.cli.process_context import multiprocess_execution


logger = logging.getLogger(__name__)
POLL_INTERVAL = 0.05
TERMINATE_TIMEOUT = 5.0
KILL_TIMEOUT = 5.0
MIN_WORKER_ARGUMENTS = 2


def run_single_process(app_path: str, arguments: list[str]) -> None:
    application_object = import_app_object(app_path)
    application_object.run(arguments)


def _request_selected_worker_stop(application: Any, arguments: list[str]) -> bool:
    if len(arguments) < MIN_WORKER_ARGUMENTS or arguments[0] not in {"run", "cron"} or arguments[1] == "all":
        return False
    get_workers = getattr(application, "get_registered_workers", None)
    if callable(get_workers):
        for worker in get_workers():
            if worker.name == arguments[1]:
                worker.request_stop()
                return True
    return False


def _watch_for_stop(application: Any, arguments: list[str], stop: Connection, finished: threading.Event) -> None:
    requested = False
    while not finished.wait(POLL_INTERVAL):
        requested = requested or stop.poll()
        if not requested:
            continue
        try:
            stop_application = getattr(application, "stop", None)
            if callable(stop_application):
                # Repeat during startup: BoostApp.stop() before the coordinator
                # starts deliberately has no effect on a future run.
                stop_application()
            if _request_selected_worker_stop(application, arguments):
                return
        except BaseException:
            logger.exception("Failed to request application shutdown in child process")
            return


def _run_child_process(app_path: str, arguments: list[str], stop: Connection, process_count: int = 1) -> None:
    # The parent owns SIGINT and coordinates shutdown through a one-way pipe.
    # Reset an inherited SIGTERM handler so terminate() remains the forced step.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    try:
        if stop.poll():
            return
        application = import_app_object(app_path)
        if stop.poll():
            return
        finished = threading.Event()
        watcher = threading.Thread(
            target=_watch_for_stop, args=(application, arguments, stop, finished), name="process-stop", daemon=True
        )
        watcher.start()
        try:
            with multiprocess_execution(process_count):
                application.run(arguments)
        finally:
            finished.set()
            watcher.join(timeout=POLL_INTERVAL)
    finally:
        stop.close()


class _ProcessSupervisor:
    def __init__(self, app_path: str, count: int, arguments: list[str], shutdown_timeout: float) -> None:
        self._app_path = app_path
        self._count = count
        self._arguments = arguments
        self._shutdown_timeout = shutdown_timeout
        self._stops: dict[Process, Connection] = {}
        self._processes: list[Process] = []
        self._running: list[Process] = []
        self._forced: set[Process] = set()
        self._error: BaseException | None = None
        self._signal: int | None = None

    def run(self) -> None:
        previous_handlers: dict[signal.Signals, Any] = {}
        try:
            if threading.current_thread() is threading.main_thread():
                for signum in (signal.SIGINT, signal.SIGTERM):
                    previous_handlers[signum] = signal.signal(signum, self._handle_signal)
            try:
                self._start()
                while self._running and self._signal is None and self._error is None:
                    self._poll_children()
                    if self._running and self._error is None:
                        time.sleep(POLL_INTERVAL)
            except BaseException as exc:
                self._record_error("Process supervision failed", exc)
            finally:
                self._cleanup()
        finally:
            for previous_signum, handler in previous_handlers.items():
                signal.signal(previous_signum, handler)
        if self._error is not None:
            if isinstance(self._error, SystemExit) and (self._error.code is None or self._error.code == 0):
                raise RuntimeError("Process supervision failed with a success exit code") from self._error
            raise self._error
        if self._signal is not None:
            raise SystemExit(128 + self._signal)

    def _handle_signal(self, signum: int, _frame: FrameType | None) -> None:
        # No locks, IPC, or cleanup in a signal handler. Repeats retain the first
        # signal and do not reset or shorten the cleanup deadlines.
        if self._signal is None:
            self._signal = signum

    def _record_error(self, source: str, error: BaseException) -> None:
        logger.error("%s", source, exc_info=(type(error), error, error.__traceback__))  # noqa: LOG014
        if self._error is None:
            self._error = error

    def _start(self) -> None:
        for index in range(self._count):
            self._poll_children()
            if self._signal is not None or self._error is not None:
                break
            child_stop, parent_stop = Pipe(duplex=False)
            try:
                process = Process(
                    target=_run_child_process,
                    args=(self._app_path, self._arguments, child_stop, self._count),
                    name=f"worker-{index}",
                )
            except BaseException:
                child_stop.close()
                parent_stop.close()
                raise
            # Track the object before start(): a partial start must also clean up.
            self._processes.append(process)
            self._running.append(process)
            self._stops[process] = parent_stop
            try:
                process.start()
            finally:
                child_stop.close()
            logger.info("Started process %s (PID: %s)", process.name, process.pid)

    def _poll_children(self) -> None:
        for process in list(self._running):
            exit_code = process.exitcode
            if exit_code is None:
                continue
            self._running.remove(process)
            if exit_code != 0 and process not in self._forced:
                status = exit_code if exit_code > 0 else 128 - exit_code
                self._record_error(
                    f"Process {process.name} (PID: {process.pid}) exited with code {exit_code}", SystemExit(status)
                )
            else:
                logger.info("Process %s exited with code %s", process.name, exit_code)
            try:
                process.join(timeout=0)
            except BaseException as exc:
                self._record_error(f"Could not join process {process.name}", exc)

    def _wait(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while self._running:
            self._poll_children()
            remaining = deadline - time.monotonic()
            if not self._running or remaining <= 0:
                return
            time.sleep(min(POLL_INTERVAL, remaining))

    def _force(self, method: str) -> None:
        for process in self._running:
            try:
                if process.is_alive():
                    self._forced.add(process)
                    logger.warning("Escalating process shutdown: %s %s (PID: %s)", method, process.name, process.pid)
                    getattr(process, method)()
            except BaseException as exc:  # noqa: PERF203 - one failed stop must not skip the remaining children
                self._record_error(f"Could not {method} process {process.name}", exc)

    def _cleanup(self) -> None:
        self._request_stop()
        self._running = [process for process in self._running if process.pid is not None]
        for method, timeout in (
            (None, self._shutdown_timeout),
            ("terminate", TERMINATE_TIMEOUT),
            ("kill", KILL_TIMEOUT),
        ):
            if method is not None:
                self._force(method)
            try:
                self._wait(timeout)
            except BaseException as exc:
                self._record_error("Error while waiting for child shutdown", exc)
        for process in self._processes:
            try:
                if process.is_alive():
                    raise TimeoutError(f"Process {process.name} (PID: {process.pid}) survived kill timeout")
                try:
                    if process.pid is not None:
                        process.join(timeout=0)
                finally:
                    process.close()
            except BaseException as exc:  # noqa: PERF203 - one failed close must not skip the remaining children
                self._record_error(f"Could not release process {process.name}", exc)

    def _request_stop(self) -> None:
        for process, connection in self._stops.items():
            try:
                if process.pid is not None and process.exitcode is None:
                    # One tiny message per dedicated pipe cannot fill its buffer.
                    # No shared lock can be abandoned by an unexpectedly dead child.
                    connection.send_bytes(b"stop")
            except (BrokenPipeError, EOFError):  # noqa: PERF203 - one failed stop must not skip the remaining children
                logger.debug("Stop pipe for process %s was already closed", process.name)
            except BaseException as exc:
                self._record_error(f"Could not request stop for process {process.name}", exc)
            finally:
                try:
                    connection.close()
                except BaseException as exc:
                    self._record_error(f"Could not close stop pipe for process {process.name}", exc)


def run_multiprocess(
    app_path: str, number_of_processes: int, arguments: list[str], *, shutdown_timeout: float = 30.0
) -> None:
    """Supervise children, requesting cooperative stop before bounded escalation.

    Raises:
        ValueError: If the process count or shutdown timeout is invalid.
    """
    if number_of_processes < 1:
        raise ValueError("number_of_processes must be positive")
    if not math.isfinite(shutdown_timeout) or shutdown_timeout < 0:
        raise ValueError("shutdown_timeout must be a finite, non-negative number of seconds")
    _ProcessSupervisor(app_path, number_of_processes, list(arguments), shutdown_timeout).run()
