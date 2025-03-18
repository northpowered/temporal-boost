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
        **asgi_worker_kwargs: Any,
    ) -> None:
        self.name = "uvicorn"
        self._app = app
        self._host = host
        self._port = port
        self._log_level = log_level
        self._asgi_worker_kwargs = asgi_worker_kwargs

        self._server: Any = None

    def run(self) -> None:
        try:
            import uvicorn  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("uvicorn is not installed.") from exc

        config = uvicorn.Config(
            app=self._app,
            host=self._host,
            port=self._port,
            log_level=self._log_level,
            log_config=None,
            proxy_headers=True,
            **self._asgi_worker_kwargs,
        )
        self._server = uvicorn.Server(config=config)
        self._server.run()

    async def shutdown(self) -> None:
        if not self._server:
            return
        await self._server.shutdown()
