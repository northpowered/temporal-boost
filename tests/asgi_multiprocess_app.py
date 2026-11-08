"""Port-binding probe for external ASGI launch policy, without optional backends."""

import os
import socket
from pathlib import Path
from unittest.mock import patch

from temporal_boost import BaseAsgiWorker, BoostApp
from temporal_boost.workers.temporal import TemporalBoostWorker


def record(role: str) -> None:
    (Path(os.environ["ASGI_TEST_RESULTS"]) / f"{role}.{os.getpid()}").touch()


class PortBindingWorker(BaseAsgiWorker):
    def run(self) -> None:
        record("http-started")
        with socket.socket() as listener:
            listener.bind((self._host, self._port))
            listener.listen()
            record("http-bound")


class RecordingTemporalWorker(TemporalBoostWorker):
    def run(self) -> None:
        record("consumer")

    def cron(self) -> None:
        record("cron")


async def activity() -> None:
    pass


def mark(target: str = "all") -> None:
    record(f"exec-{target}")


app = BoostApp(logger_config=None)
with patch("temporal_boost.boost_app.get_asgi_worker_class", return_value=PortBindingWorker):
    app.add_asgi_worker("http", "unused:app", "127.0.0.1", int(os.environ["ASGI_TEST_PORT"]))
with patch("temporal_boost.boost_app.TemporalBoostWorker", RecordingTemporalWorker):
    app.add_worker("consumer", "unused-queue", activities=[activity], cron_schedule="* * * * *", cron_runner=activity)
app.add_exec_method_sync("mark", mark)
