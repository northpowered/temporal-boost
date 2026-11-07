"""Subprocess fixture: signals never reach the pytest process."""

import asyncio
import signal
import sys
from pathlib import Path

from temporal_boost import AsyncBoostWorker, BoostApp


class SignalWorker(AsyncBoostWorker):
    name = "signal-worker"

    def __init__(self, result_file: Path) -> None:
        super().__init__()
        self.result_file = result_file
        self.finish: asyncio.Event | None = None
        self.owner_loop: asyncio.AbstractEventLoop | None = None
        self.shutdown_calls = 0

    async def run_async(self) -> None:
        self.owner_loop = asyncio.get_running_loop()
        self.finish = asyncio.Event()
        print("READY", flush=True)  # noqa: T201
        await self.finish.wait()
        with self.result_file.open("a") as output:
            output.write("returned\n")

    async def shutdown(self) -> None:
        assert asyncio.get_running_loop() is self.owner_loop
        self.shutdown_calls += 1
        print("CLEANUP", flush=True)  # noqa: T201
        assert await asyncio.to_thread(sys.stdin.readline) == "finish\n"
        self.result_file.write_text(f"cleanup:{self.shutdown_calls}\n")
        assert self.finish is not None
        self.finish.set()


def main() -> None:
    result_file = Path(sys.argv[1])
    app = BoostApp(logger_config=None)
    worker = SignalWorker(result_file)
    app.add_async_runtime(worker.name, worker)
    previous_handlers = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}
    app.run_all_workers()
    for signum, handler in previous_handlers.items():
        assert signal.getsignal(signum) == handler
    with result_file.open("a") as output:
        output.write("restored\n")


if __name__ == "__main__":
    main()
