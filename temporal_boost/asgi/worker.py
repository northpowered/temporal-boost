import typing
import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve


if typing.TYPE_CHECKING:
    from core import BoostApp


class ASGIWorker:
    def __init__(
        self,
        app: "BoostApp",
        asgi_app: typing.Any,
        worker_name: str,
        host: str,
        port: int,
    ) -> None:
        self.app = app
        self.worker_name = worker_name
        self.host: str = host
        self.port: int = port
        self.asgi_app: typing.Any = asgi_app

    async def _run_worker(self) -> int:
        config: Config = Config()
        # Provide Base logger to ASGI as an extra arg
        self.asgi_app.logger = self.app.logger
        # Supressing default hypercorn loggers
        config.accesslog = None
        config.errorlog = None
        # Serving params config
        config.bind = [f"{self.host}:{self.port}"]
        # ASGI corutine
        await serve(self.asgi_app, config, mode="asgi")

    def run(self):
        asyncio.run(self._run_worker())
        return self.worker_name
