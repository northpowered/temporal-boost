import asyncio
import logging
from typing import Any

from temporal_boost.workers.asgi_registry import ASGIWorkerType, asgi_worker_registry
from temporal_boost.workers.base import BaseAsgiWorker


logger = logging.getLogger(__name__)


@asgi_worker_registry.register(ASGIWorkerType.hypercorn.value, packages=["hypercorn"])
class HypercornBoostWorker(BaseAsgiWorker):
    def __init__(
        self,
        app: Any,
        host: str,
        port: int,
        *,
        log_level: str | int | None = None,
        **asgi_worker_kwargs: Any,
    ) -> None:
        self.name = "hypercorn"
        self._app = app
        self._host = host
        self._port = port
        self._log_level = log_level
        self._asgi_worker_kwargs = asgi_worker_kwargs

        self._server_task: asyncio.Task[Any] | None = None

    def run(self) -> None:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._run_server())

    async def _run_server(self) -> None:
        try:
            from hypercorn.asyncio import serve  # noqa: PLC0415
            from hypercorn.config import Config  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("hypercorn is not installed.") from exc

        config = Config()
        config.bind = [f"{self._host}:{self._port}"]
        if self._log_level is not None:
            config.loglevel = str(self._log_level)

        for key, value in self._asgi_worker_kwargs.items():
            setattr(config, key, value)

        await serve(self._app, config, mode="asgi")

    async def shutdown(self) -> None:
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                logger.info("Hypercorn server shutdown complete.")
        else:
            raise RuntimeError("Hypercorn server is not running; cannot shutdown.")
