"""Run with: uv run python examples/example_custom_worker.py run all; Ctrl+C stops the worker."""

import asyncio
import logging

from temporal_boost import AsyncBoostWorker, BaseBoostWorker, BoostApp


logger = logging.getLogger(__name__)


class ServiceWorker(AsyncBoostWorker):
    def __init__(self) -> None:
        super().__init__()
        self.finished: asyncio.Event | None = None

    async def run_async(self) -> None:
        self.finished = asyncio.Event()
        logger.info("Running %s", self.name)
        await self.finished.wait()

    async def shutdown(self) -> None:
        if self.finished is not None:
            self.finished.set()
        logger.info("Stopped %s", self.name)


def create_app() -> BoostApp:
    app = BoostApp("custom-worker-example")
    worker: BaseBoostWorker = ServiceWorker()
    app.add_async_runtime("service", worker)
    return app


if __name__ == "__main__":
    create_app().run()
