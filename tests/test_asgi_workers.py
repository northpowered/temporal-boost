import asyncio
import builtins
import logging
import subprocess  # noqa: S404
import sys
import threading
from collections.abc import Iterator
from concurrent.futures import CancelledError as FutureCancelledError
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from temporal_boost.workers.asgi import ManagedAsgiWorker, load_asgi_app
from temporal_boost.workers.granian_worker import GranianBoostWorker
from temporal_boost.workers.hypercorn_worker import HypercornBoostWorker
from temporal_boost.workers.uvicorn_worker import UvicornBoostWorker


WAIT = 3.0
BACKENDS = {"uvicorn": UvicornBoostWorker, "hypercorn": HypercornBoostWorker, "granian": GranianBoostWorker}


async def application(_scope: Any, _receive: Any, _send: Any) -> None:
    pass


class BackendDouble:
    def __init__(self, backend: str) -> None:
        self.backend = backend
        self.options: dict[str, Any] = {}
        self.ready = threading.Event()
        self.startup_release = threading.Event()
        self.startup_release.set()
        self.cleanup_started = threading.Event()
        self.cleanup_release = threading.Event()
        self.cleanup_release.set()
        self.start_error: BaseException | None = None
        self.serve_error: BaseException | None = None
        self.cleanup_error: BaseException | None = None
        self.start_hook: Any = None
        self.starts = 0
        self.stops = 0
        self.loops: list[asyncio.AbstractEventLoop] = []

    async def start(self) -> None:
        self.starts += 1
        self.loops.append(asyncio.get_running_loop())
        self.ready.set()
        assert await asyncio.to_thread(self.startup_release.wait, WAIT)
        if self.start_hook is not None:
            await self.start_hook()
        if self.start_error is not None:
            raise self.start_error

    async def cleanup(self) -> None:
        self.stops += 1
        self.loops.append(asyncio.get_running_loop())
        self.cleanup_started.set()
        assert await asyncio.to_thread(self.cleanup_release.wait, WAIT)
        if self.cleanup_error is not None:
            raise self.cleanup_error

    def worker(self, app: Any = application, **options: Any) -> ManagedAsgiWorker:
        return BACKENDS[self.backend](app, "127.0.0.1", 8080, **options)

    def uvicorn_api(self) -> Any:
        harness = self

        def config(**options: Any) -> Any:
            return SimpleNamespace(**options)

        class UvicornServer:
            def __init__(self, config: Any) -> None:
                harness.options = vars(config)
                self.started = self.should_exit = False
                self.lifespan = SimpleNamespace(should_exit=False)

            async def startup(self, sockets: Any = None) -> None:  # noqa: ARG002
                await harness.start()
                self.started = True

            async def shutdown(self, sockets: Any = None) -> None:  # noqa: ARG002
                await harness.cleanup()

            async def serve(self) -> None:
                await self.startup()
                if self.should_exit:
                    return  # Uvicorn 0.35 skips shutdown in this branch.
                if harness.serve_error is not None:
                    raise harness.serve_error
                while not self.should_exit:  # noqa: ASYNC110 - reproduce Uvicorn's public should_exit polling
                    await asyncio.sleep(0.001)
                await self.shutdown()

        return SimpleNamespace(Config=config, Server=UvicornServer)

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        harness = self

        async def hypercorn_serve(app: Any, config: Any, *, mode: str, shutdown_trigger: Any) -> None:
            assert mode == "asgi"
            harness.options = {**vars(config), "app": app}
            await harness.start()
            await shutdown_trigger()
            await harness.cleanup()

        class GranianServer:
            def __init__(self, **options: Any) -> None:
                harness.options = options
                self.stop_event = asyncio.Event()

            def stop(self) -> None:
                self.stop_event.set()

            async def serve(self) -> None:
                await harness.start()
                await self.stop_event.wait()
                await harness.cleanup()

        monkeypatch.setitem(sys.modules, "uvicorn", self.uvicorn_api())
        monkeypatch.setitem(sys.modules, "hypercorn.asyncio", SimpleNamespace(serve=hypercorn_serve))
        monkeypatch.setitem(
            sys.modules,
            "hypercorn.config",
            SimpleNamespace(Config=lambda: SimpleNamespace(bind=[], loglevel="INFO", logconfig_dict=None, backlog=100)),
        )
        monkeypatch.setitem(sys.modules, "granian.server.embed", SimpleNamespace(Server=GranianServer))
        monkeypatch.setitem(sys.modules, "granian.constants", SimpleNamespace(Interfaces=SimpleNamespace(ASGI="asgi")))
        monkeypatch.setitem(sys.modules, "granian.log", SimpleNamespace(LogLevels=lambda value: value))


@pytest.fixture(params=list(BACKENDS))
def backend(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> BackendDouble:
    double = BackendDouble(request.param)
    double.install(monkeypatch)
    return double


@contextmanager
def running(worker: ManagedAsgiWorker) -> Iterator[tuple[threading.Thread, list[BaseException]]]:
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
        worker.request_stop()
        thread.join(WAIT)
        assert not thread.is_alive(), "ASGI worker did not stop"


def test_repeated_stop_closes_once_on_owning_loop_and_forwards_options(backend: BackendDouble) -> None:
    config = {"version": 1}
    worker = backend.worker(log_level=logging.INFO, log_config=config, backlog=256)
    assert worker.name == backend.backend
    with running(worker) as (thread, errors):
        assert backend.ready.wait(WAIT)
        for _ in range(3):
            assert worker.request_stop()
        thread.join(WAIT)
    assert errors == []
    assert backend.starts == backend.stops == 1
    assert len(set(backend.loops)) == 1
    assert backend.loops[0].is_closed()
    assert not asyncio.all_tasks(backend.loops[0])
    assert backend.options["backlog"] == 256
    app_key = "target" if backend.backend == "granian" else "app"
    forwarded = backend.options[app_key]
    if backend.backend == "granian":
        forwarded = forwarded.app
    assert forwarded is application
    logging_key = {"uvicorn": "log_config", "hypercorn": "logconfig_dict", "granian": "log_dictconfig"}[backend.backend]
    assert backend.options[logging_key] is config


@pytest.mark.asyncio
async def test_idle_shutdown_early_stop_restart_and_foreign_loop(backend: BackendDouble) -> None:
    worker = backend.worker()
    await worker.shutdown()
    assert worker.request_stop()
    await asyncio.to_thread(worker.run)
    await worker.shutdown()
    assert backend.starts == backend.stops == 0
    worker.request_stop()  # Late requests do not carry into a new run.
    with running(worker):
        assert await asyncio.to_thread(backend.ready.wait, WAIT)
        with pytest.raises(RuntimeError, match="request_stop"):
            await worker.shutdown()
    assert backend.stops == 1


def test_stop_during_startup_still_completes_lifespan_cleanup(backend: BackendDouble) -> None:
    backend.startup_release.clear()
    worker = backend.worker()
    with running(worker) as (thread, errors):
        try:
            assert backend.ready.wait(WAIT)
            worker.request_stop()
            assert thread.is_alive()
        finally:
            backend.startup_release.set()
        thread.join(WAIT)
    assert errors == []
    assert backend.stops == 1


@pytest.mark.parametrize("failure", [RuntimeError("startup failed"), KeyboardInterrupt(), SystemExit(7)])
def test_startup_failure_reaches_caller_and_idle_shutdown_is_safe(
    backend: BackendDouble, failure: BaseException
) -> None:
    backend.start_error = failure
    worker = backend.worker()
    with running(worker) as (thread, errors):
        thread.join(WAIT)
    assert len(errors) == 1
    assert errors[0] is failure
    asyncio.run(worker.shutdown())
    assert backend.stops == 0


def test_cleanup_failure_reaches_caller_without_repeating_cleanup(backend: BackendDouble) -> None:
    failure = backend.cleanup_error = ValueError("shutdown failed")
    worker = backend.worker()
    with running(worker) as (thread, errors):
        assert backend.ready.wait(WAIT)
        worker.request_stop()
        thread.join(WAIT)
    assert len(errors) == 1
    assert errors[0] is failure
    assert backend.stops == 1


def test_concurrent_run_is_rejected(backend: BackendDouble) -> None:
    worker = backend.worker()
    with running(worker):
        assert backend.ready.wait(WAIT)
        with pytest.raises(RuntimeError, match="already running"):
            worker.run()


def test_shutdown_from_server_callback_is_rejected(backend: BackendDouble) -> None:
    worker = backend.worker()
    backend.start_hook = worker.shutdown
    with running(worker) as (thread, errors):
        thread.join(WAIT)
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert "request_stop" in str(errors[0])


@pytest.mark.parametrize("failure", [ValueError("serve failed"), asyncio.CancelledError(), FutureCancelledError()])
def test_uvicorn_serve_error_survives_cleanup_error(monkeypatch: pytest.MonkeyPatch, failure: BaseException) -> None:
    backend = BackendDouble("uvicorn")
    backend.install(monkeypatch)
    backend.serve_error = failure
    backend.cleanup_error = RuntimeError("cleanup failed")
    with running(backend.worker()) as (thread, errors):
        thread.join(WAIT)
    assert errors[0] is (failure if isinstance(failure, ValueError) else backend.cleanup_error)
    assert backend.stops == 1


@pytest.mark.parametrize("backend_name", list(BACKENDS))
def test_backend_process_managers_are_rejected(backend_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = BackendDouble(backend_name)
    backend.install(monkeypatch)
    with pytest.raises(ValueError, match="workers=1"):
        backend.worker(workers=2).run()
    reloader = "use_reloader" if backend_name == "hypercorn" else "reload"
    with pytest.raises(ValueError, match="False"):
        backend.worker(**{reloader: True}).run()
    assert backend.starts == 0


def test_hypercorn_unknown_option_is_not_silently_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = BackendDouble("hypercorn")
    backend.install(monkeypatch)
    with pytest.raises(ValueError, match=r"Unsupported Hypercorn.*typo_option"):
        backend.worker(typo_option=1).run()


def test_custom_event_loop_modes_are_rejected(backend: BackendDouble) -> None:
    options = {"worker_class": "trio"} if backend.backend == "hypercorn" else {"loop": "uvloop"}
    with pytest.raises(ValueError, match="asyncio"):
        backend.worker(**options).run()
    assert backend.starts == 0


def test_application_import_paths_and_callability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "asgi_unit_app", SimpleNamespace(nested=SimpleNamespace(app=application)))
    assert load_asgi_app("asgi_unit_app:nested.app") is application
    assert load_asgi_app(application) is application
    with pytest.raises(ValueError, match="module:attribute"):
        load_asgi_app("asgi_unit_app")
    with pytest.raises(TypeError, match="callable"):
        load_asgi_app(object())


def test_missing_backend_has_installation_hint(backend: BackendDouble, monkeypatch: pytest.MonkeyPatch) -> None:
    original = builtins.__import__

    def without_backend(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.partition(".")[0] == backend.backend:
            raise ModuleNotFoundError(name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_backend)
    with pytest.raises(RuntimeError, match=rf"temporal-boost\[{backend.backend}\]"):
        backend.worker().run()


def test_package_imports_without_asgi_extras() -> None:
    script = """
import importlib.abc
import sys
class WithoutBackends(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'uvicorn', 'hypercorn', 'granian'}:
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, WithoutBackends())
import temporal_boost
from temporal_boost.workers.asgi_registry import asgi_worker_registry
assert not asgi_worker_registry.available_keys()
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=10, check=False)  # noqa: S603
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
async def test_shutdown_waiters_and_owner_cancellation_join_cleanup(backend: BackendDouble) -> None:
    backend.cleanup_release.clear()
    worker = backend.worker()
    owner = asyncio.create_task(worker._run_managed())
    try:
        assert await asyncio.to_thread(backend.ready.wait, WAIT)
        first = asyncio.create_task(worker.shutdown())
        second = asyncio.create_task(worker.shutdown())
        assert await asyncio.to_thread(backend.cleanup_started.wait, WAIT)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        owner.cancel("first")
        await asyncio.sleep(0)
        owner.cancel("repeated")
        await asyncio.sleep(0)
        assert not owner.done()
    finally:
        backend.cleanup_release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(second, WAIT)
    result = await asyncio.wait_for(owner, WAIT)
    assert isinstance(result, asyncio.CancelledError)
    assert backend.stops == 1


def smoke(backend: str, mode: str, target: str) -> None:
    pytest.importorskip(backend)
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", "from tests.asgi_lifecycle_app import main; main()", backend, mode, target],
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("backend", ["uvicorn", "granian"])
def test_real_backend_factory(backend: str) -> None:
    smoke(backend, "thread", "factory")


@pytest.mark.parametrize("backend", list(BACKENDS))
@pytest.mark.parametrize("mode", ["startup-failure", "shutdown-failure", "bind-failure"])
def test_real_backend_lifespan_failure_is_fatal(backend: str, mode: str) -> None:
    smoke(backend, mode, "object")


@pytest.mark.parametrize("backend", ["uvicorn", "hypercorn", "granian"])
@pytest.mark.parametrize("mode", ["main", "thread", "coordinator", "SIGINT", "SIGTERM"])
@pytest.mark.parametrize("target", ["object", "string"])
def test_real_backend_http_lifespan_and_managed_stop(backend: str, mode: str, target: str) -> None:
    smoke(backend, mode, target)
