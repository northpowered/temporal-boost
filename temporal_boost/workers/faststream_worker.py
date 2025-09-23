import asyncio
import logging
from typing import Any

from temporal_boost.workers.base import BaseBoostWorker


logger = logging.getLogger(__name__)


class FastStreamBoostWorker(BaseBoostWorker):
    def __init__(
        self,
        app: Any,
        *,
        log_level: str | int | None = None,
        **faststream_kwargs: Any,
    ) -> None:
        self.name = "faststream"
        self._app = app
        self._log_level = log_level or logging.INFO
        self._faststream_kwargs = faststream_kwargs

    def run(self) -> None:
        try:
            import anyio  # noqa: PLC0415
            from faststream import FastStream  # noqa: PLC0415

            if not isinstance(self._app, FastStream):
                raise TypeError(f"Expected FastStream instance, got {type(self._app)}")
        except ImportError as exc:
            raise RuntimeError("faststream is not installed.") from exc

        if self._log_level is not None:
            logging.getLogger("faststream").setLevel(self._log_level)

        try:
            logger.info(f"Starting FastStream worker '{self.name}'")
            anyio.run(
                self._app.run,  # type: ignore[arg-type]
                self._log_level,
                self._faststream_kwargs,
            )
        except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
            logger.info("Received interrupt signal, initiating shutdown")
        except Exception:
            logger.exception("Error during FastStream application run")
            raise
        finally:
            asyncio.run(self.shutdown())

    async def shutdown(self) -> None:
        logger.info(f"FastStream worker '{self.name}' shutdown completed")
