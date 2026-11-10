import asyncio
import selectors
import signal
import subprocess  # noqa: S404
import sys
import threading
import time
from collections.abc import Iterator
from concurrent.futures import CancelledError as FutureCancelledError
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from temporal_boost import AsyncBoostWorker, BaseBoostWorker, BoostApp


WAIT_TIMEOUT = 5.0


class ControlledWorker(AsyncBoostWorker):
    def __init__(self, name: str = "controlled") -> None:
        super().__init__()
        self.name = name
        self.ready = threading.Event()
        self.cleanup_started = threading.Event()
        self.cleanup_release = threading.Event()
        self.cleanup_release.set()
        self.returned = threading.Event()
        self.shutdown_calls = 0
        self.owner_loop: asyncio.AbstractEventLoop | None = None
        self.cleanup_loop: asyncio.AbstractEventLoop | None = None
        self.owner_thread: int | None = None
        self.run_thread: threading.Thread | None = None
        self.cleanup_thread: int | None = None
        self.finish: asyncio.Event | None = None

    async def run_async(self) -> None:
        self.owner_loop = asyncio.get_running_loop()
        self.owner_thread = threading.get_ident()
        self.run_thread = threading.current_thread()
        self.finish = asyncio.Event()
        self.ready.set()
        await self.finish.wait()
        self.returned.set()

    async def shutdown(self) -> None:
        self.shutdown_calls += 1
        self.cleanup_loop = asyncio.get_running_loop()
        self.cleanup_thread = threading.get_ident()
        self.cleanup_started.set()
        assert await asyncio.to_thread(self.cleanup_release.wait, WAIT_TIMEOUT)
        assert self.finish is not None
        self.finish.set()


@contextmanager
def running_app(app: BoostApp) -> Iterator[tuple[threading.Thread, list[BaseException]]]:
    errors: list[BaseException] = []

    def run() -> None:
        try:
            app.run_all_workers()
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        yield thread, errors
    finally:
        for worker in app.get_registered_workers():
            if isinstance(worker, ControlledWorker):
                worker.cleanup_release.set()
        app.stop()
        thread.join(WAIT_TIMEOUT)
        assert not thread.is_alive(), "Coordinator did not return"
        for worker in app.get_registered_workers():
            if isinstance(worker, ControlledWorker) and worker.run_thread is not None:
                worker.run_thread.join(WAIT_TIMEOUT)
                assert not worker.run_thread.is_alive(), "Worker thread did not return"


def test_stop_waits_for_cleanup_on_each_workers_own_loop() -> None:
    app = BoostApp(logger_config=None)
    workers = [ControlledWorker("first"), ControlledWorker("second")]
    for worker in workers:
        worker.cleanup_release.clear()
        app.add_async_runtime(worker.name, worker)

    with running_app(app) as (thread, errors):
        for worker in workers:
            assert worker.ready.wait(WAIT_TIMEOUT)
        app.stop()
        for worker in workers:
            assert worker.cleanup_started.wait(WAIT_TIMEOUT)
        for _ in range(10):
            app.stop()
        assert thread.is_alive()
        for worker in workers:
            worker.cleanup_release.set()
        thread.join(WAIT_TIMEOUT)

    assert errors == []
    for worker in workers:
        assert worker.returned.is_set()
        assert worker.shutdown_calls == 1
        assert worker.cleanup_loop is worker.owner_loop
        assert worker.cleanup_thread == worker.owner_thread
        assert worker.cleanup_thread != threading.get_ident()
        assert worker.owner_loop is not None
        assert worker.owner_loop.is_closed()
    assert workers[0].owner_loop is not workers[1].owner_loop


def test_stop_before_worker_loop_starts_is_remembered() -> None:
    worker = ControlledWorker()
    app = BoostApp(logger_config=None)
    app.add_async_runtime(worker.name, worker)

    original_run = worker.run

    def run() -> None:
        worker.request_stop()
        worker.request_stop()
        app.stop()
        original_run()

    with patch.object(worker, "run", side_effect=run):
        with running_app(app) as (thread, errors):
            thread.join(WAIT_TIMEOUT)

    assert errors == []
    assert worker.returned.is_set()
    assert worker.shutdown_calls == 1


def test_stop_is_idle_safe_and_app_can_run_again() -> None:
    app = BoostApp(logger_config=None)
    worker = ControlledWorker()
    app.add_async_runtime(worker.name, worker)
    app.stop()

    for _ in range(2):
        worker.ready.clear()
        worker.returned.clear()
        with running_app(app) as (thread, errors):
            assert worker.ready.wait(WAIT_TIMEOUT)
            app.stop()
            thread.join(WAIT_TIMEOUT)
        assert errors == []
        assert worker.returned.is_set()
        app.stop()
    assert worker.shutdown_calls == 2


@pytest.mark.parametrize("shutdown_timeout", [-1, float("nan"), float("inf"), -float("inf")])
def test_shutdown_timeout_must_be_finite_and_non_negative(shutdown_timeout: float) -> None:
    with pytest.raises(ValueError, match="shutdown_timeout"):
        BoostApp(logger_config=None, shutdown_timeout=shutdown_timeout)


def test_zero_shutdown_timeout_is_accepted() -> None:
    app = BoostApp(logger_config=None, shutdown_timeout=0)
    app.run_all_workers()


def test_hung_workers_share_one_shutdown_deadline_and_prevent_restart() -> None:
    app = BoostApp(logger_config=None, shutdown_timeout=0.1)
    workers = [ControlledWorker("first"), ControlledWorker("second")]
    for worker in workers:
        worker.cleanup_release.clear()
        app.add_async_runtime(worker.name, worker)

    with running_app(app) as (thread, errors):
        for worker in workers:
            assert worker.ready.wait(WAIT_TIMEOUT)
        started = time.monotonic()
        app.stop()
        thread.join(WAIT_TIMEOUT)
        elapsed = time.monotonic() - started
        assert not thread.is_alive()
        assert len(errors) == 1
        assert isinstance(errors[0], TimeoutError)
        assert "first, second" in str(errors[0])
        assert 0.1 <= elapsed < 1.0
        for worker in workers:
            assert worker.cleanup_started.is_set()
        with pytest.raises(RuntimeError, match="previous run"):
            app.run_all_workers()

    for worker in workers:
        assert worker.returned.wait(WAIT_TIMEOUT)


def test_concurrent_run_is_rejected() -> None:
    app = BoostApp(logger_config=None)
    worker = ControlledWorker()
    app.add_async_runtime(worker.name, worker)
    with running_app(app):
        assert worker.ready.wait(WAIT_TIMEOUT)
        with pytest.raises(RuntimeError, match="already running"):
            app.run_all_workers()


def test_background_coordinator_does_not_install_signal_handlers() -> None:
    app = BoostApp(logger_config=None)
    worker = ControlledWorker()
    app.add_async_runtime(worker.name, worker)
    with patch("temporal_boost.worker_coordinator.signal.signal") as install:
        with running_app(app):
            assert worker.ready.wait(WAIT_TIMEOUT)
        install.assert_not_called()


def test_partial_thread_start_failure_stops_started_workers() -> None:
    app = BoostApp(logger_config=None)
    first, second = ControlledWorker("first"), ControlledWorker("second")
    app.add_async_runtime(first.name, first)
    app.add_async_runtime(second.name, second)
    original_start = threading.Thread.start
    previous_handlers = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}

    def start(thread: threading.Thread) -> None:
        if thread.name == "worker-second":
            assert first.ready.wait(WAIT_TIMEOUT)
            raise RuntimeError("cannot start thread")
        original_start(thread)

    with patch.object(threading.Thread, "start", start), pytest.raises(RuntimeError, match="cannot start thread"):
        app.run_all_workers()

    assert first.returned.is_set()
    assert first.shutdown_calls == 1
    assert not second.ready.is_set()
    for signum, handler in previous_handlers.items():
        assert signal.getsignal(signum) == handler


class LegacyWorker(BaseBoostWorker):
    name = "legacy"

    def __init__(self) -> None:
        self.ready = threading.Event()
        self.release = threading.Event()
        self.run_thread: threading.Thread | None = None

    def run(self) -> None:
        self.run_thread = threading.current_thread()
        self.ready.set()
        self.release.wait(WAIT_TIMEOUT)

    async def shutdown(self) -> None:
        pytest.fail("Coordinator must not call async cleanup on an arbitrary loop")


def test_unsupported_worker_is_reported_and_wait_is_bounded(caplog: pytest.LogCaptureFixture) -> None:
    app = BoostApp(logger_config=None, shutdown_timeout=0.01)
    worker = LegacyWorker()
    app.add_async_runtime(worker.name, worker)
    try:
        with running_app(app) as (thread, errors):
            assert worker.ready.wait(WAIT_TIMEOUT)
            app.stop()
            thread.join(WAIT_TIMEOUT)
        assert len(errors) == 1
        assert isinstance(errors[0], TimeoutError)
        assert "legacy" in str(errors[0])
        assert "does not support managed stopping" in caplog.text
    finally:
        worker.release.set()
        if worker.run_thread is not None:
            worker.run_thread.join(WAIT_TIMEOUT)
            assert not worker.run_thread.is_alive()


class ExitingWorker(BaseBoostWorker):
    name = "exiting"

    def __init__(self, peer_ready: threading.Event, error: BaseException | None = None) -> None:
        self.peer_ready = peer_ready
        self.error = error

    def run(self) -> None:
        assert self.peer_ready.wait(WAIT_TIMEOUT)
        if self.error is not None:
            raise self.error

    async def shutdown(self) -> None:
        pytest.fail("Coordinator must use request_stop(), not async shutdown()")


def test_unexpected_return_is_fatal_and_stops_peer() -> None:
    app = BoostApp(logger_config=None)
    peer = ControlledWorker()
    exiting = ExitingWorker(peer.ready)
    app.add_async_runtime(exiting.name, exiting)
    app.add_async_runtime(peer.name, peer)

    with running_app(app) as (thread, errors):
        thread.join(WAIT_TIMEOUT)

    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert "exiting" in str(errors[0])
    assert "returned before shutdown" in str(errors[0])
    assert peer.returned.is_set()


def test_first_failure_survives_peer_cleanup_failure(caplog: pytest.LogCaptureFixture) -> None:
    primary = RuntimeError("first failure")
    secondary = ValueError("peer cleanup failed")

    class CleanupFailingWorker(ControlledWorker):
        async def shutdown(self) -> None:
            await super().shutdown()
            raise secondary

    app = BoostApp(logger_config=None)
    peer = CleanupFailingWorker()
    exiting = ExitingWorker(peer.ready, primary)
    app.add_async_runtime(exiting.name, exiting)
    app.add_async_runtime(peer.name, peer)

    with running_app(app) as (thread, errors):
        thread.join(WAIT_TIMEOUT)

    assert errors == [primary]
    assert errors[0] is primary
    assert peer.cleanup_started.is_set()
    assert "peer cleanup failed" in caplog.text
    logged_error = next(
        record.exc_info for record in caplog.records if record.exc_info and record.exc_info[1] is secondary
    )
    assert logged_error is not None
    assert logged_error[2] is not None


def test_first_failure_survives_shutdown_timeout(caplog: pytest.LogCaptureFixture) -> None:
    app = BoostApp(logger_config=None, shutdown_timeout=0.01)
    primary = RuntimeError("first failure")
    peer = ControlledWorker()
    peer.cleanup_release.clear()
    exiting = ExitingWorker(peer.ready, primary)
    app.add_async_runtime(exiting.name, exiting)
    app.add_async_runtime(peer.name, peer)

    with running_app(app) as (thread, errors):
        thread.join(WAIT_TIMEOUT)
        assert not thread.is_alive()
        assert errors == [primary]
        assert errors[0] is primary
        assert peer.cleanup_started.is_set()
        assert "Workers did not stop within" in caplog.text
        assert peer.name in caplog.text
        with pytest.raises(RuntimeError, match="previous run"):
            app.run_all_workers()


@pytest.mark.parametrize("cancellation", [asyncio.CancelledError(), FutureCancelledError()])
def test_cancellation_after_stop_is_normal_shutdown(cancellation: BaseException) -> None:
    app = BoostApp(logger_config=None)
    worker = ControlledWorker()
    app.add_async_runtime(worker.name, worker)
    original_run = worker.run

    def run() -> None:
        original_run()
        raise cancellation

    with patch.object(worker, "run", side_effect=run):
        with running_app(app) as (thread, errors):
            assert worker.ready.wait(WAIT_TIMEOUT)
            app.stop()
            thread.join(WAIT_TIMEOUT)

    assert errors == []
    assert worker.returned.is_set()


@pytest.mark.parametrize("failure", [RuntimeError("shutdown failed"), KeyboardInterrupt(), SystemExit(0)])
def test_failure_after_stop_is_not_suppressed(failure: BaseException) -> None:
    app = BoostApp(logger_config=None)
    worker = ControlledWorker()
    app.add_async_runtime(worker.name, worker)
    original_run = worker.run

    def run() -> None:
        original_run()
        raise failure

    with patch.object(worker, "run", side_effect=run):
        with running_app(app) as (thread, errors):
            assert worker.ready.wait(WAIT_TIMEOUT)
            app.stop()
            thread.join(WAIT_TIMEOUT)

    assert errors == [failure]
    assert errors[0] is failure


def test_async_run_error_survives_own_cleanup_failure(caplog: pytest.LogCaptureFixture) -> None:
    primary = RuntimeError("run failed")
    cleanup_called = threading.Event()

    class BrokenWorker(AsyncBoostWorker):
        name = "broken"

        async def run_async(self) -> None:
            raise primary

        async def shutdown(self) -> None:
            cleanup_called.set()
            raise ValueError("own cleanup failed")

    app = BoostApp(logger_config=None)
    worker = BrokenWorker()
    app.add_async_runtime(worker.name, worker)
    with pytest.raises(RuntimeError, match="run failed") as raised:
        app.run_all_workers()

    assert raised.value is primary
    assert cleanup_called.is_set()
    assert "own cleanup failed" in caplog.text


@pytest.mark.parametrize("cancellation", [asyncio.CancelledError(), FutureCancelledError()])
def test_async_cancellation_does_not_hide_cleanup_failure(cancellation: BaseException) -> None:
    app = BoostApp(logger_config=None)
    cleanup_error = RuntimeError("cleanup failed during cancellation")

    class CancellingWorker(AsyncBoostWorker):
        name = "cancelling"

        async def run_async(self) -> None:
            app.stop()
            raise cancellation

        async def shutdown(self) -> None:
            raise cleanup_error

    worker = CancellingWorker()
    app.add_async_runtime(worker.name, worker)
    with pytest.raises(RuntimeError, match="cleanup failed during cancellation") as raised:
        app.run_all_workers()

    assert raised.value is cleanup_error


@pytest.mark.parametrize("failure", [RuntimeError("stop request failed"), SystemExit(1)])
def test_stop_request_failure_does_not_skip_remaining_workers(failure: BaseException) -> None:
    class StopFailingWorker(ControlledWorker):
        def request_stop(self) -> bool:
            super().request_stop()
            raise failure

    app = BoostApp(logger_config=None)
    first, second = StopFailingWorker("first"), ControlledWorker("second")
    app.add_async_runtime(first.name, first)
    app.add_async_runtime(second.name, second)

    with running_app(app) as (thread, errors):
        assert first.ready.wait(WAIT_TIMEOUT)
        assert second.ready.wait(WAIT_TIMEOUT)
        app.stop()
        thread.join(WAIT_TIMEOUT)

    assert errors == [failure]
    assert errors[0] is failure
    assert first.returned.is_set()
    assert second.returned.is_set()


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_signals_stop_workers_and_restore_handlers_in_subprocess(signum: signal.Signals, tmp_path: Path) -> None:
    result_file = tmp_path / "lifecycle.txt"
    script = Path(__file__).parent / "signal_shutdown_app.py"
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "-u", str(script), str(result_file)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        cwd=Path(__file__).resolve().parents[1],
    )
    try:
        assert process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(WAIT_TIMEOUT), "Subprocess did not become ready"
            assert process.stdout.readline() == b"READY\n"
            process.send_signal(signum)
            assert selector.select(WAIT_TIMEOUT), "Cleanup did not start"
            assert process.stdout.readline() == b"CLEANUP\n"
            # Exercise a repeated signal while the first shutdown is in progress.
            process.send_signal(signum)
        stdout, stderr = process.communicate(input=b"finish\n", timeout=WAIT_TIMEOUT)
        assert process.returncode == 0, (stdout, stderr)
        assert result_file.read_text() == "cleanup:1\nreturned\nrestored\n"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=WAIT_TIMEOUT)
