import subprocess
import asyncio


class BoostHTTPWorker:

    def __init__(
        self,
        worker_name: str,
        host: str,
        port: int,
        route: str,
        app: str

    ) -> None:
        self.worker_name = worker_name,
        self.host: str = host
        self.port: int = port
        self.route: str = route
        self.app: str = app

    async def _run(self) -> int:
        # !!! https://superfastpython.com/asyncio-subprocess/
        proc = subprocess.Popen(
            [
                "granian",
                "--host",
                self.host,
                "--port",
                str(self.port),
                "--interface",
                "asgi",
                "--url-path-prefix",
                self.route,
                "--threading-mode",
                "runtime",
                "--no-ws",
                "--loop",
                "asyncio",
                self.app
            ],
            stdout=subprocess.DEVNULL
        )
        proc.wait()

    async def run(self):
        asyncio.run(self._run())
        return self.worker_name
