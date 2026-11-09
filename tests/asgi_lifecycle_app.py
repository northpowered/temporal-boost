"""Real ASGI lifecycle probe, executed in isolated subprocesses by the smoke tests."""

import asyncio
import json
import os
import signal
import socket
import sys
import threading
import time
from http.client import HTTPConnection
from typing import Any

import pytest

from temporal_boost import ASGIWorkerType, BoostApp
from temporal_boost.workers.base import BaseBoostWorker
from temporal_boost.workers.granian_worker import GranianBoostWorker
from temporal_boost.workers.hypercorn_worker import HypercornBoostWorker
from temporal_boost.workers.uvicorn_worker import UvicornBoostWorker


WAIT = 5.0
events: list[str] = []
loops: list[asyncio.AbstractEventLoop] = []
scenario = ""


async def asgi_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    loops.append(asyncio.get_running_loop())
    if scope["type"] == "lifespan":
        assert (await receive())["type"] == "lifespan.startup"
        events.append("startup")
        if scenario == "startup-failure":
            await send({"type": "lifespan.startup.failed", "message": "startup probe failed"})
            return
        scope["state"]["ready"] = True
        await send({"type": "lifespan.startup.complete"})
        assert (await receive())["type"] == "lifespan.shutdown"
        events.append("shutdown")
        if scenario == "shutdown-failure":
            await send({"type": "lifespan.shutdown.failed", "message": "shutdown probe failed"})
            return
        await send({"type": "lifespan.shutdown.complete"})
    elif scope["type"] == "http":
        assert scope["state"]["ready"]
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"managed-asgi"})


def factory() -> Any:
    events.append("factory")
    return asgi_app


def request(port: int) -> None:
    deadline = time.monotonic() + WAIT
    while True:
        connection = HTTPConnection("127.0.0.1", port, timeout=0.5)
        try:
            connection.request("GET", "/probe")
            response = connection.getresponse()
            assert response.status == 200
            assert response.read() == b"managed-asgi"
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)
        finally:
            connection.close()


def client(worker: BaseBoostWorker, application: BoostApp, mode: str, port: int, errors: list[BaseException]) -> None:
    try:
        request(port)
        if mode in {"SIGINT", "SIGTERM"}:
            os.kill(os.getpid(), getattr(signal, mode))
        elif mode == "coordinator":
            application.stop()
        else:
            worker.request_stop()
    except BaseException as exc:
        errors.append(exc)
        application.stop()
        worker.request_stop()


def run(worker: BaseBoostWorker, application: BoostApp, mode: str, errors: list[BaseException]) -> None:
    if mode == "thread":

        def serve() -> None:
            try:
                worker.run()
            except BaseException as exc:
                errors.append(exc)

        serving = threading.Thread(target=serve, daemon=True)
        serving.start()
        serving.join(WAIT + 1)
        assert not serving.is_alive(), "server thread did not stop"
    elif mode == "coordinator":
        application.run_all_workers()
    else:
        worker.run()


def bind_failure(worker: BaseBoostWorker, port: int) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", port))
        listener.listen()
        with pytest.raises((OSError, RuntimeError, SystemExit)) as caught:
            worker.run()
        if isinstance(caught.value, SystemExit):
            assert caught.value.code == 1
        else:
            assert "address already in use" in str(caught.value).lower()
    for loop in loops:
        assert loop.is_closed()
        assert not asyncio.all_tasks(loop)


def main() -> None:
    global scenario  # noqa: PLW0603 - subprocess fixture configures the ASGI probe
    backend, mode, target = sys.argv[1:]
    scenario = mode
    classes = {"uvicorn": UvicornBoostWorker, "hypercorn": HypercornBoostWorker, "granian": GranianBoostWorker}
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    options: dict[str, Any] = {"log_level": "error"}
    app: Any = asgi_app if target == "object" else "tests.asgi_lifecycle_app:asgi_app"
    if target == "factory":
        app = "tests.asgi_lifecycle_app:factory"
        options["factory"] = True
    worker = classes[backend](app, "127.0.0.1", port, **options)
    if mode == "bind-failure":
        bind_failure(worker, port)
        return
    application = BoostApp(logger_config=None, shutdown_timeout=WAIT)
    if mode == "coordinator":
        application.add_asgi_worker("http", app, "127.0.0.1", port, asgi_worker_type=ASGIWorkerType(backend), **options)
        worker = application.get_registered_workers()[0]
    if mode == "startup-failure":
        with pytest.raises(Exception, match=r"(?i)startup"):
            worker.run()
        assert events == ["startup"]
        assert not asyncio.all_tasks(loops[0])
        return
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    errors: list[BaseException] = []
    sender = threading.Thread(target=client, args=(worker, application, mode, port, errors), daemon=True)
    sender.start()
    if mode == "shutdown-failure":
        with pytest.raises(Exception, match=r"(?i)(lifespan|shutdown)"):
            run(worker, application, mode, errors)
    else:
        run(worker, application, mode, errors)
    sender.join(WAIT + 1)
    assert not sender.is_alive()
    assert not errors, errors
    assert events.count("startup") == events.count("shutdown") == 1, events
    if target == "factory":
        assert events.count("factory") == 1
    assert len(set(loops)) == 1
    assert loops[0].is_closed()
    assert not asyncio.all_tasks(loops[0])
    assert previous == {sig: signal.getsignal(sig) for sig in previous}
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            raise AssertionError("server is still listening after shutdown")
    except OSError:
        pass
    sys.stdout.write(json.dumps({"backend": backend, "events": events}) + "\n")
