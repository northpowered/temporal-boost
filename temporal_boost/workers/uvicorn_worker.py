import asyncio
import logging
from typing import Any

from temporal_boost.workers.asgi_registry import ASGIWorkerType, asgi_worker_registry
from temporal_boost.workers.base import BaseAsgiWorker


logger = logging.getLogger(__name__)


@asgi_worker_registry.register(ASGIWorkerType.uvicorn.value, packages=["uvicorn"])
class UvicornBoostWorker(BaseAsgiWorker):
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
        self.name = "uvicorn"
        super().__init__(
            app,
            host,
            port,
            log_level=log_level,
            log_config=log_config,
            **asgi_worker_kwargs,
        )
        self._server: Any = None

    def run(self) -> None:
        try:
            import uvicorn  # type: ignore[import-not-found]  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("uvicorn is not installed.") from exc

        config = uvicorn.Config(
            app=self._app,
            host=self._host,
            port=self._port,
            log_level=self._log_level,
            log_config=self._log_config,
            **self._asgi_worker_kwargs,
        )
        self._server = uvicorn.Server(config=config)
        try:
            self._server.run()
        except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
            logger.info("Received interrupt signal, initiating shutdown")
        except Exception:
            logger.exception("Error during application run")
            raise
        finally:
            asyncio.run(self.shutdown())

    async def shutdown(self) -> None:
        if not self._server:
            return
        await self._server.shutdown()
