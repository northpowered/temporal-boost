import asyncio
import typing
from dataclasses import dataclass

from robyn import Robyn, config

if typing.TYPE_CHECKING:
    from temporal_boost.core import BoostApp


class InternalWorker:
    def __init__(
        self,
        app: "BoostApp",
        worker_name: str,
        host: str,
        port: int,
    ) -> None:
        self.app = app
        self.worker_name = worker_name
        self.host: str = host
        self.port: int = port
        # Creating robyn app for internal web server
        robyn_config = config
        # Suppressing robyn rust logger
        config.log_level = "ERROR"
        self.web_app = Robyn("__internal__", config=robyn_config)

    def run(self):
        self.web_app.start(port=self.port, host=self.host)
        return self.worker_name
