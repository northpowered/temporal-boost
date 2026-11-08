from __future__ import annotations

import asyncio
import inspect
import logging
import signal
import subprocess  # noqa: S404
import sys
import threading
from contextlib import asynccontextmanager, contextmanager
from importlib.metadata import version
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from temporal_boost import BoostApp
from temporal_boost.workers.faststream_worker import FastStreamBoostWorker


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator


WAIT = 3.0


class BrokerDouble:
    def __init__(self) -> None:
        self.stop_calls = 0
        self.loop: asyncio.AbstractEventLoop | None = None
        self.failure: BaseException | None = None

    async def stop(self) -> None:
        self.stop_calls += 1
        self.loop = asyncio.get_running_loop()
        if self.failure is not None:
            raise self.failure


class AppDouble:
    def __init__(self) -> None:
        self.broker: BrokerDouble | None = BrokerDouble()
        self.ready = threading.Event()
        self.cleanup_started = threading.Event()
        self.cleanup_release = threading.Event()
        self.cleanup_release.set()
        self.startup_cancelled = threading.Event()
        self.block_start = False
        self.start_error: BaseException | None = None
        self.stop_error: BaseException | None = None
        self.enter_error: BaseException | None = None
        self.exit_error: BaseException | None = None
        self.start_options: dict[str, Any] | None = None
        self.lifespan_options: dict[str, Any] | None = None
        self.stop_calls = 0
        self.enters = 0
        self.exits = 0
        self.start_loop: asyncio.AbstractEventLoop | None = None
        self.stop_loop: asyncio.AbstractEventLoop | None = None
        self.start_hook: Any = None

    @asynccontextmanager
    async def lifespan_context(self, **options: Any) -> AsyncIterator[None]:
        import anyio  # noqa: PLC0415

        if self.enter_error is not None:
            raise self.enter_error
        self.enters += 1
        self.lifespan_options = options
        owner = asyncio.current_task()
        # AnyIO scopes must enter and exit in the same task, not just the same loop.
        async with anyio.create_task_group():
            try:
                yield
            finally:
                assert asyncio.current_task() is owner
                self.exits += 1
                if self.exit_error is not None:
                    raise self.exit_error

    async def start(self, **options: Any) -> None:
        self.start_options = options
        self.start_loop = asyncio.get_running_loop()
        self.ready.set()
        if self.start_hook is not None:
            await self.start_hook()
        if self.start_error is not None:
            raise self.start_error
        if self.block_start:
            try:
                await asyncio.Event().wait()
            finally:
                self.startup_cancelled.set()

    async def stop(self) -> None:
        self.stop_calls += 1
        self.stop_loop = asyncio.get_running_loop()
        self.cleanup_started.set()
        assert await asyncio.to_thread(self.cleanup_release.wait, WAIT)
        if self.stop_error is not None:
            raise self.stop_error
        if self.broker is not None:
            await self.broker.stop()


@pytest.fixture
def application(monkeypatch: pytest.MonkeyPatch) -> Iterator[AppDouble]:
    monkeypatch.setitem(sys.modules, "faststream", SimpleNamespace(FastStream=AppDouble))
    previous_level = logging.getLogger("faststream").level
    yield AppDouble()
    logging.getLogger("faststream").setLevel(previous_level)


@contextmanager
def running_worker(worker: FastStreamBoostWorker) -> Iterator[tuple[threading.Thread, list[BaseException]]]:
    errors: list[BaseException] = []

    def run() -> None:
        try:
            worker.run()
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        yield thread, errors
    finally:
        if isinstance(worker._app, AppDouble):
            worker._app.cleanup_release.set()
        worker.request_stop()
        thread.join(WAIT)
        assert not thread.is_alive(), "FastStream worker did not return"


def test_thread_stop_closes_broker_and_lifespan_once_on_owner_loop(application: AppDouble) -> None:
    worker = FastStreamBoostWorker(application, log_level=0, region="west", attempts=2)
    with running_worker(worker) as (thread, errors):
        assert application.ready.wait(WAIT)
        for _ in range(5):
            assert worker.request_stop()
        thread.join(WAIT)
    assert errors == []
    assert application.start_options == application.lifespan_options == {"region": "west", "attempts": 2}
    assert application.stop_calls == application.enters == application.exits == 1
    assert application.broker is not None
    assert application.broker.stop_calls == 1
    assert application.start_loop is application.stop_loop is application.broker.loop
    assert application.start_loop is not None
    assert application.start_loop.is_closed()
    assert logging.getLogger("faststream").level == 0


def test_stop_during_startup_cancels_start_before_closing_broker(application: AppDouble) -> None:
    application.block_start = True
    worker = FastStreamBoostWorker(application)
    with running_worker(worker) as (thread, errors):
        assert application.ready.wait(WAIT)
        worker.request_stop()
        thread.join(WAIT)
    assert errors == []
    assert application.startup_cancelled.is_set()
    assert application.stop_calls == 1
    assert application.broker is not None
    assert application.broker.stop_calls == 1


@pytest.mark.asyncio
async def test_idle_shutdown_early_stop_and_restart(application: AppDouble) -> None:
    worker = FastStreamBoostWorker(application)
    await worker.shutdown()
    assert worker.request_stop()
    await asyncio.to_thread(worker.run)
    assert application.enters == application.stop_calls == 0
    await worker.shutdown()
    worker.request_stop()  # A late request must not prevent the next run.
    with running_worker(worker) as (thread, errors):
        assert application.ready.wait(WAIT)
        worker.request_stop()
        thread.join(WAIT)
    assert errors == []
    assert application.stop_calls == 1


@pytest.mark.parametrize(
    "failure",
    [RuntimeError("startup failed"), KeyboardInterrupt(), SystemExit(0), SystemExit(7), asyncio.CancelledError()],
)
def test_startup_failure_preserves_identity_after_cleanup(application: AppDouble, failure: BaseException) -> None:
    application.start_error = failure
    worker = FastStreamBoostWorker(application)
    with running_worker(worker) as (thread, errors):
        thread.join(WAIT)
    assert errors == [failure]
    assert errors[0] is failure
    assert application.stop_calls == application.exits == 1
    assert application.broker is not None
    assert application.broker.stop_calls == 1


@pytest.mark.parametrize("cancelled", [False, True])
def test_cleanup_failure_preserves_primary_and_attempts_broker_stop(
    application: AppDouble, cancelled: bool, caplog: pytest.LogCaptureFixture
) -> None:
    primary = asyncio.CancelledError() if cancelled else RuntimeError("startup failed")
    cleanup = ValueError("shutdown hook failed")
    application.start_error = primary
    application.stop_error = cleanup
    worker = FastStreamBoostWorker(application)
    with running_worker(worker) as (thread, errors):
        thread.join(WAIT)
    assert errors[0] is (cleanup if cancelled else primary)
    assert application.broker is not None
    assert application.broker.stop_calls == 1
    assert "shutdown completed" not in caplog.text
    if not cancelled:
        assert "shutdown hook failed" in caplog.text


def test_lifespan_failure_does_not_mask_startup_failure(application: AppDouble) -> None:
    primary = ValueError("startup failed")
    application.start_error = primary
    application.exit_error = RuntimeError("lifespan close failed")
    with running_worker(FastStreamBoostWorker(application)) as (thread, errors):
        thread.join(WAIT)
    assert errors[0] is primary
    assert application.stop_calls == 1


def test_lifespan_enter_failure_does_not_claim_broker_shutdown(
    application: AppDouble, caplog: pytest.LogCaptureFixture
) -> None:
    failure = RuntimeError("lifespan enter failed")
    application.enter_error = failure
    with running_worker(FastStreamBoostWorker(application)) as (thread, errors):
        thread.join(WAIT)
    assert errors[0] is failure
    assert application.stop_calls == 0
    assert "shutdown completed" not in caplog.text


def test_lifespan_background_failure_closes_broker(
    application: AppDouble, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import anyio  # noqa: PLC0415

    failure = ValueError("lifespan background failed")

    async def fail() -> None:
        assert await asyncio.to_thread(application.ready.wait, WAIT)
        raise failure

    @asynccontextmanager
    async def lifespan(**_options: Any) -> AsyncIterator[None]:
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(fail)
            yield

    assert application.broker is not None
    stop_broker = application.broker.stop

    async def close() -> None:
        await anyio.lowlevel.checkpoint()
        await stop_broker()

    monkeypatch.setattr(application.broker, "stop", close)
    monkeypatch.setattr(application, "lifespan_context", lifespan)
    with running_worker(FastStreamBoostWorker(application)) as (thread, errors):
        thread.join(WAIT)
    assert len(errors) == 1
    assert failure in getattr(errors[0], "exceptions", ())
    assert application.broker is not None
    assert application.broker.stop_calls == 1
    assert "shutdown completed" not in caplog.text


@pytest.mark.asyncio
async def test_shutdown_waiters_join_once_and_reject_foreign_loop(application: AppDouble) -> None:
    worker = FastStreamBoostWorker(application)
    with running_worker(worker):
        assert await asyncio.to_thread(application.ready.wait, WAIT)
        with pytest.raises(RuntimeError, match="request_stop"):
            await worker.shutdown()

    application.ready.clear()
    task = asyncio.create_task(worker._run_managed())
    assert await asyncio.to_thread(application.ready.wait, WAIT)
    await asyncio.gather(worker.shutdown(), worker.shutdown())
    assert await task is None
    await worker.shutdown()
    assert application.stop_calls == 2


@pytest.mark.asyncio
async def test_repeated_cancellation_waits_for_same_task_lifespan_cleanup(application: AppDouble) -> None:
    application.cleanup_release.clear()
    worker = FastStreamBoostWorker(application)
    task = asyncio.create_task(worker._run_managed())
    try:
        assert await asyncio.to_thread(application.ready.wait, WAIT)
        task.cancel("first")
        assert await asyncio.to_thread(application.cleanup_started.wait, WAIT)
        task.cancel("repeat")
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        application.cleanup_release.set()
        result = await asyncio.wait_for(task, WAIT)
    assert isinstance(result, asyncio.CancelledError)
    assert application.stop_calls == application.exits == 1


def test_concurrent_run_is_rejected(application: AppDouble) -> None:
    worker = FastStreamBoostWorker(application)
    with running_worker(worker):
        assert application.ready.wait(WAIT)
        with pytest.raises(RuntimeError, match="already running"):
            worker.run()


def test_shutdown_from_lifecycle_callback_is_rejected(application: AppDouble) -> None:
    worker = FastStreamBoostWorker(application)
    application.start_hook = worker.shutdown
    with running_worker(worker) as (thread, errors):
        thread.join(WAIT)
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert "request_stop" in str(errors[0])


@pytest.mark.parametrize("missing", ["faststream", "anyio"])
def test_missing_dependency_has_clear_error_without_success_log(
    monkeypatch: pytest.MonkeyPatch, missing: str, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setitem(sys.modules, missing, None)
    with pytest.raises(RuntimeError, match=r"Install temporal-boost\[faststream\]"):
        FastStreamBoostWorker(object()).run()
    assert "shutdown completed" not in caplog.text


@pytest.mark.usefixtures("application")
def test_invalid_application_is_rejected_before_cleanup(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(TypeError, match="Expected FastStream"):
        FastStreamBoostWorker(object()).run()
    assert "shutdown completed" not in caplog.text


def test_base_package_imports_without_optional_dependencies() -> None:
    script = """
import importlib.abc
import sys
class WithoutExtras(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'faststream', 'anyio'}:
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, WithoutExtras())
import temporal_boost
from temporal_boost.workers import FastStreamBoostWorker
try:
    FastStreamBoostWorker(object()).run()
except RuntimeError as exc:
    assert 'temporal-boost[faststream]' in str(exc)
else:
    raise AssertionError('missing extra was accepted')
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=10, check=False)  # noqa: S603
    assert result.returncode == 0, result.stdout + result.stderr


def test_coordinator_stops_faststream_without_touching_signal_handlers(application: AppDouble) -> None:
    app = BoostApp(logger_config=None, shutdown_timeout=2)
    app.add_faststream_worker("messages", application)
    errors: list[BaseException] = []

    def run() -> None:
        try:
            app.run_all_workers()
        except BaseException as exc:
            errors.append(exc)

    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        assert application.ready.wait(WAIT)
        app.stop()
    finally:
        app.stop()
        thread.join(WAIT)
    assert not thread.is_alive()
    assert errors == []
    assert application.stop_calls == 1
    assert handlers == {sig: signal.getsignal(sig) for sig in handlers}


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_main_thread_signal_stops_worker_and_restores_handlers(signum: signal.Signals) -> None:
    script = """
import os
import signal
import sys
import threading
from types import SimpleNamespace
from tests.test_faststream_worker import AppDouble, WAIT
from temporal_boost.workers.faststream_worker import FastStreamBoostWorker
sys.modules['faststream'] = SimpleNamespace(FastStream=AppDouble)
application = AppDouble()
worker = FastStreamBoostWorker(application)
handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
def interrupt():
    if application.ready.wait(WAIT):
        os.kill(os.getpid(), int(sys.argv[1]))
    else:
        worker.request_stop()
sender = threading.Thread(target=interrupt, daemon=True)
sender.start()
worker.run()
sender.join(WAIT)
assert application.ready.is_set()
assert application.stop_calls == application.exits == application.broker.stop_calls == 1
assert handlers == {sig: signal.getsignal(sig) for sig in handlers}
"""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, str(int(signum))], capture_output=True, text=True, timeout=10, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
async def test_real_faststream_in_memory_broker_lifecycle_and_options() -> None:
    faststream = pytest.importorskip("faststream")
    redis = pytest.importorskip("faststream.redis")
    assert version("faststream") == "0.5.48"
    broker = redis.RedisBroker("redis://unused:6379")
    loops: list[asyncio.AbstractEventLoop] = []
    events: list[str] = []

    @asynccontextmanager
    async def lifespan(region: str) -> AsyncIterator[None]:
        import anyio  # noqa: PLC0415

        assert region == "west"
        async with anyio.create_task_group():
            events.append("lifespan-enter")
            yield
            events.append("lifespan-exit")

    app = faststream.FastStream(broker, lifespan=lifespan, logger=None)
    worker = FastStreamBoostWorker(app, region="west")
    bound = inspect.signature(app.run).bind(logging.INFO, {"region": "west"})
    assert bound.arguments["run_extra_options"] == {"region": "west"}

    @broker.subscriber("probe")
    async def consume(message: str) -> None:
        assert message == "hello"
        loops.append(asyncio.get_running_loop())
        events.append("message")

    @app.on_startup
    async def startup(region: str) -> None:
        assert region == "west"
        loops.append(asyncio.get_running_loop())
        events.append("startup")

    @app.after_startup
    async def started() -> None:
        await broker.publish("hello", "probe")
        worker.request_stop()

    @app.after_shutdown
    async def stopped() -> None:
        loops.append(asyncio.get_running_loop())
        events.append("shutdown")

    async with redis.TestRedisBroker(broker, connect_only=True):
        stop = broker.stop
        await asyncio.wait_for(asyncio.to_thread(worker.run), WAIT)
        stop.assert_awaited_once()
        assert events == ["lifespan-enter", "startup", "message", "shutdown", "lifespan-exit"]
    assert len(set(loops)) == 1
    assert loops[0].is_closed()
