import subprocess
import asyncio
import granian

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

    def _run_worker(self) -> int:
        # !!! https://superfastpython.com/asyncio-subprocess/
        # proc = await asyncio.create_subprocess_exec( 
        #     "granian",
        #     "--host",
        #     self.host,
        #     "--port",
        #     str(self.port),
        #     "--interface",
        #     "asgi",
        #     "--url-path-prefix",
        #     self.route,
        #     "--threading-mode",
        #     "runtime",
        #     "--no-ws",
        #     "--loop",
        #     "asyncio",
        #     self.app,
        #     stdout=subprocess.DEVNULL
        # )
        

        # await proc.wait()
        server = granian.server.Granian(
            target=self.app,
            address=self.host,
            port=self.port,
            interface="asgi",
            threading_mode="runtime",
            websockets=False,
            loop="asyncio"
        
            
        )
        server.serve(None,None)

    def run(self):
        self._run_worker()
        #asyncio.run(self._run_worker())
        return self.worker_name
