"""Subprocess fixture for real process supervision without external services."""

import asyncio
import multiprocessing
import os
import signal
import sys
import time
from pathlib import Path

from temporal_boost import AsyncBoostWorker, BaseBoostWorker, BoostApp
from temporal_boost.cli import process_runner


def result_path(suffix: str) -> Path:
    return Path(os.environ["SUPERVISION_RESULTS"]) / f"{multiprocessing.current_process().name}.{suffix}"


class CooperativeWorker(AsyncBoostWorker):
    name = "service"

    def __init__(self) -> None:
        super().__init__()
        self.finish: asyncio.Event | None = None

    async def run_async(self) -> None:
        self.finish = asyncio.Event()
        result_path("ready").write_text(str(os.getpid()))
        if os.environ["SUPERVISION_MODE"] == "fail-second" and multiprocessing.current_process().name == "worker-1":
            first_ready = result_path("ready").with_name("worker-0.ready")
            while not first_ready.exists():  # noqa: ASYNC110 - the file is a cross-process readiness gate
                await asyncio.sleep(0.01)
            raise RuntimeError("second child failed while first was running")
        await self.finish.wait()
        result_path("returned").write_text("returned")

    async def shutdown(self) -> None:
        result_path("cleanup").write_text(str(time.monotonic()))
        release = result_path("ready").with_name("release")
        while not release.exists():  # noqa: ASYNC110 - the test process releases this cross-process gate
            await asyncio.sleep(0.01)
        if self.finish is not None:
            self.finish.set()


class StubbornWorker(BaseBoostWorker):
    name = "service"

    def run(self) -> None:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        result_path("ready").write_text(str(os.getpid()))
        while True:
            time.sleep(0.1)

    async def shutdown(self) -> None:
        pass


app = BoostApp(logger_config=None, shutdown_timeout=1)
app.add_async_runtime(
    "service", StubbornWorker() if os.getenv("SUPERVISION_MODE") == "stubborn" else CooperativeWorker()
)


def fail_start() -> None:
    deadline = time.monotonic() + 5
    while not result_path("ready").with_name("worker-0.ready").exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("first child did not start")
        time.sleep(0.01)
    raise RuntimeError("injected second start failure")


def main() -> None:
    mode, directory, command = sys.argv[1:]
    os.environ["SUPERVISION_MODE"] = mode
    os.environ["SUPERVISION_RESULTS"] = directory
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = directory
    if mode == "stubborn":
        process_runner.TERMINATE_TIMEOUT = 0.2
        process_runner.KILL_TIMEOUT = 1
    if mode == "start-failure":
        original_process = process_runner.Process

        def make_process(**kwargs: object) -> multiprocessing.Process:
            process = original_process(**kwargs)
            if process.name == "worker-1":
                process.start = fail_start
            return process

        process_runner.Process = make_process
    handlers = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}
    try:
        process_runner.run_multiprocess(
            "tests.process_supervision_app:app", 2, ["run", command], shutdown_timeout=0.3 if mode == "stubborn" else 2
        )
    finally:
        assert not multiprocessing.active_children(), "supervisor left live children"
        assert handlers == {signum: signal.getsignal(signum) for signum in handlers}
        (Path(directory) / "reaped").write_text("handlers restored; no children")


if __name__ == "__main__":
    main()
