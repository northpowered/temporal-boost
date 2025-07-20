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
        log_config: dict[str, Any] | None = None,
        **asgi_worker_kwargs: Any,
    ) -> None:
        self.name = "hypercorn"
        super().__init__(
            app,
            host,
            port,
            log_level=log_level,
            log_config=log_config,
            **asgi_worker_kwargs,
        )
        self._server_task: asyncio.Task[Any] | None = None

    def run(self) -> None:
        asyncio.run(self._run_server())

    async def _run_server(self) -> None:
        try:
            from hypercorn.asyncio import serve  # type: ignore[import-not-found]  # noqa: PLC0415
            from hypercorn.config import Config  # type: ignore[import-not-found]  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("hypercorn is not installed.") from exc

        config = Config()
        config.bind = [f"{self._host}:{self._port}"]
        if self._log_level is not None:
            config.loglevel = str(self._log_level)

        config.logconfig_dict = self._log_config

        for key, value in self._asgi_worker_kwargs.items():
            setattr(config, key, value)

        self._server_task = asyncio.create_task(serve(self._app, config, mode="asgi"))
        try:
            await self._server_task
        except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
            logger.info("Received interrupt signal, initiating shutdown")
        except Exception:
            logger.exception("Error during application run")
            raise
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                logger.info("Hypercorn server shutdown complete.")
        else:
            msg = "Hypercorn server is not running; cannot shutdown."
            raise RuntimeError(msg)
