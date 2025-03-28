from typing import Any

from temporal_boost.workers.asgi_registry import ASGIWorkerType, asgi_worker_registry
from temporal_boost.workers.base import BaseAsgiWorker


@asgi_worker_registry.register(ASGIWorkerType.granian.value, packages=["granian"])
class GranianBoostWorker(BaseAsgiWorker):
    def __init__(
        self,
        app: Any,
        host: str,
        port: int,
        *,
        log_level: str | None = None,
        **asgi_worker_kwargs: Any,
    ) -> None:
        self.name = "granian"
        self._app = app
        self._host = host
        self._port = port
        self._log_level = log_level
        self._asgi_worker_kwargs = asgi_worker_kwargs

        self._server: Any = None

    def run(self) -> None:
        try:
            from granian.constants import Interfaces  # noqa: PLC0415
            from granian.log import LogLevels  # noqa: PLC0415
            from granian.server import Server  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("granian is not installed.") from exc

        self._server = Server(
            target=self._app,
            address=self._host,
            interface=Interfaces.ASGI,
            port=self._port,
            log_level=LogLevels(self._log_level.lower()) if self._log_level else LogLevels.debug,
            **self._asgi_worker_kwargs,
        )
        self._server.serve()

    async def shutdown(self) -> None:
        if not self._server:
            return
        self._server.shutdown()
