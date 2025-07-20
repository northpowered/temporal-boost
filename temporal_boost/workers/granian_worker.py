import asyncio
import logging
from typing import Any

from temporal_boost.workers.asgi_registry import ASGIWorkerType, asgi_worker_registry
from temporal_boost.workers.base import BaseAsgiWorker


logger = logging.getLogger(__name__)


@asgi_worker_registry.register(ASGIWorkerType.granian.value, packages=["granian"])
class GranianBoostWorker(BaseAsgiWorker):
    def __init__(
        self,
        app: Any,
        host: str,
        port: int,
        *,
        log_level: str | None = None,
        log_config: dict[str, Any] | None = None,
        **asgi_worker_kwargs: Any,
    ) -> None:
        self.name = "granian"
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
            from granian.constants import Interfaces  # type: ignore[import-not-found]  # noqa: PLC0415
            from granian.log import LogLevels  # type: ignore[import-not-found]  # noqa: PLC0415
            from granian.server import Server  # type: ignore[import-not-found]  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("granian is not installed.") from exc

        log_level_str = str(self._log_level).lower() if self._log_level else "debug"
        self._server = Server(
            target=self._app,
            address=self._host,
            interface=Interfaces.ASGI,
            port=self._port,
            log_level=LogLevels(log_level_str),
            log_dictconfig=self._log_config,
            **self._asgi_worker_kwargs,
        )
        try:
            self._server.serve()
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
        self._server.shutdown()
