import asyncio
import logging
from typing import Any

from temporal_boost.workers.asgi import ManagedAsgiWorker, capture_error, load_asgi_app
from temporal_boost.workers.asgi_registry import ASGIWorkerType, asgi_worker_registry


class _LifespanObserver:
    """Retain failures Granian 2.4 otherwise only records in its lifespan handler."""

    def __init__(self, app: Any, worker: ManagedAsgiWorker) -> None:
        self.app = app
        self.worker = worker
        self.failure: BaseException | None = None
        self.started = False

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "lifespan":
            await self.app(scope, receive, send)
            return

        async def observe(message: Any) -> None:
            if message["type"].endswith(".failed"):
                self.failure = RuntimeError(f"ASGI {message['type']}: {message.get('message', '')}")
                self.worker.request_stop()
            elif message["type"] == "lifespan.startup.complete":
                self.started = True
            await send(message)

        try:
            await self.app(scope, receive, observe)
        except BaseException as exc:
            # Ordinary pre-start exceptions retain Granian's auto-detection of
            # apps without lifespan support. Fatal exceptions must reach run().
            if self.started or not isinstance(exc, Exception):
                self.failure = self.failure or exc
                self.worker.request_stop()
            if not isinstance(exc, Exception):
                stage = "shutdown" if self.started else "startup"
                await send({"type": f"lifespan.{stage}.failed", "message": str(exc)})
                return
            raise


@asgi_worker_registry.register(ASGIWorkerType.granian.value, packages=["granian"])
class GranianBoostWorker(ManagedAsgiWorker):
    def __init__(
        self,
        app: Any,
        host: str,
        port: int,
        *,
        log_level: str | int | None = None,
        log_config: dict[str, Any] | None = None,
        **asgi_worker_kwargs: Any,
    ) -> None:
        super().__init__(
            app,
            host,
            port,
            log_level=log_level,
            log_config=log_config,
            **asgi_worker_kwargs,
        )
        self.name = "granian"
        self._server: Any = None

    async def _serve(self, stop: asyncio.Event) -> None:
        try:
            from granian.constants import Interfaces  # type: ignore[import-not-found]  # noqa: PLC0415
            from granian.log import LogLevels  # type: ignore[import-not-found]  # noqa: PLC0415
            from granian.server.embed import Server  # type: ignore[import-not-found]  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("Granian embedded server is unavailable. Install temporal-boost[granian].") from exc

        options = self._asgi_worker_kwargs.copy()
        if options.pop("workers", 1) != 1 or options.pop("reload", False):
            raise ValueError("Managed Granian embedded mode requires workers=1 and reload=False")
        if options.pop("loop", "asyncio") not in {"auto", "asyncio"}:
            raise ValueError("Managed Granian uses the owning asyncio loop; custom loop options are unsupported")
        level = self._log_level
        if isinstance(level, int):
            level = logging.getLevelName(level)
        log_level_str = level.lower() if level is not None else "debug"
        app = load_asgi_app(self._app)
        if options.pop("factory", False):
            app = load_asgi_app(app())
        observer = _LifespanObserver(app, self)
        server: Any = Server(
            target=observer,
            address=self._host,
            interface=Interfaces.ASGI,
            port=self._port,
            log_level=LogLevels(log_level_str),
            log_dictconfig=self._log_config,
            **options,
        )
        self._server = server

        async def request_exit() -> None:
            server.stop()

        try:
            error = await capture_error(self._serve_until_stopped(server.serve(), stop, request_exit))
            if observer.failure is not None:
                raise observer.failure
            if error is not None:
                raise error
        finally:
            self._server = None
