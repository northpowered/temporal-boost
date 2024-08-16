from __future__ import annotations

import asyncio
import typing

import trio
from hypercorn.config import Config
from hypercorn.trio import serve

from temporal_boost.schemas import WorkerType

if typing.TYPE_CHECKING:
    from core import BoostApp


class CustomHypercornConfig(Config):
    boost_app: BoostApp | None = None



class ASGIWorker:
    def __init__(
        self,
        app: BoostApp,
        asgi_app: typing.Any,
        worker_name: str,
        host: str,
        port: int,
    ) -> None:
        self.app = app
        self.name = worker_name
        self.host: str = host
        self.port: int = port
        self.asgi_app: typing.Any = asgi_app
        self.task_queue: str = "null"  # temp fix
        self._type: WorkerType = WorkerType.ASGI
        self.description: str = ""  # create arg

    def _run_worker(self) -> int:
        config: CustomHypercornConfig = CustomHypercornConfig()
        # Provide Base logger to ASGI as an extra arg
        config.boost_app = self.app
        self.asgi_app.logger = self.app.logger
        # Supressing default hypercorn loggers
        config.accesslog = None
        # Serving params config
        config.bind = [f"{self.host}:{self.port}"]

        trio.run(serve, self.asgi_app, config)


    def run(self):
        self._run_worker()
        return self.worker_name
