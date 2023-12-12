from aiohttp import web
from dataclasses import dataclass
import typing
import asyncio

if typing.TYPE_CHECKING:
    from core import BoostApp


@dataclass
class BoostHTTPRoute:
    route: str
    handler: typing.Coroutine


class BoostHTTPWorker:
    def __init__(
        self,
        app: "BoostApp",
        worker_name: str,
        host: str,
        port: int,
        routes: list[BoostHTTPRoute],
    ) -> None:
        self.app = app
        self.worker_name = (worker_name,)
        self.host: str = host
        self.port: int = port
        self.routes: list[BoostHTTPRoute] = routes

    def _run_worker(self) -> int:
        http_app = web.Application(logger=self.app.logger)
        for route in self.routes:
            http_app.add_routes([web.get(route.route, route.handler)])
        web.run_app(app=http_app, host=self.host, port=self.port)

    def run(self):
        asyncio.run(self._run_worker())
        return self.worker_name
