import asyncio
import logging
from collections.abc import Iterator
from concurrent.futures import CancelledError as FutureCancelledError
from contextlib import contextmanager
from typing import Any

from temporal_boost.workers.asgi import ManagedAsgiWorker
from temporal_boost.workers.asgi_registry import ASGIWorkerType, asgi_worker_registry


logger = logging.getLogger(__name__)


@asgi_worker_registry.register(ASGIWorkerType.uvicorn.value, packages=["uvicorn"])
class UvicornBoostWorker(ManagedAsgiWorker):
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
        self.name = "uvicorn"
        self._server: Any = None

    def _create_server(self) -> tuple[Any, asyncio.Event]:
        try:
            import uvicorn  # type: ignore[import-not-found]  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("uvicorn is not installed. Install temporal-boost[uvicorn].") from exc

        options = self._asgi_worker_kwargs.copy()
        if options.get("workers", 1) != 1 or options.get("reload", False):
            raise ValueError("Managed Uvicorn requires workers=1 and reload=False")
        if options.get("loop", "asyncio") not in {"asyncio", "auto"}:
            raise ValueError("Managed Uvicorn uses the owning asyncio loop; custom loop options are unsupported")
        options.setdefault("workers", 1)
        ready = asyncio.Event()

        class Server(uvicorn.Server):
            shutdown_called = False

            @contextmanager
            def capture_signals(self) -> Iterator[None]:
                # ManagedAsgiWorker owns and restores main-thread handlers.
                yield

            async def startup(self, sockets: Any = None) -> None:
                await super().startup(sockets=sockets)
                if self.started:
                    ready.set()

            async def shutdown(self, sockets: Any = None) -> None:
                self.shutdown_called = True
                await super().shutdown(sockets=sockets)

        config = uvicorn.Config(
            app=self._app,
            host=self._host,
            port=self._port,
            log_level=self._log_level,
            log_config=self._log_config,
            **options,
        )
        return Server(config=config), ready

    async def _serve(self, stop: asyncio.Event) -> None:
        server, ready = self._create_server()
        self._server = server

        async def request_exit() -> None:
            # Uvicorn 0.35 returns without shutdown if should_exit is set before
            # startup finishes. Let startup finish before requesting its exit.
            await ready.wait()
            server.should_exit = True

        error: BaseException | None = None
        try:
            await self._serve_until_stopped(server.serve(), stop, request_exit)
            if not server.started:
                raise RuntimeError("Uvicorn application startup failed")
            if server.lifespan.should_exit:
                raise RuntimeError("Uvicorn application lifespan failed; see server logs")
        except BaseException as exc:
            error = exc
        finally:
            try:
                # serve() owns normal cleanup. A main-loop failure in 0.35 can
                # bypass it; only clean up a started, not-yet-stopped server.
                if server.started and not server.shutdown_called:
                    await server.shutdown()
            except BaseException:
                if error is None or isinstance(error, (asyncio.CancelledError, FutureCancelledError)):
                    raise
                logger.exception("Uvicorn cleanup failed; preserving serve error")
            finally:
                self._server = None
        if error is not None:
            raise error
