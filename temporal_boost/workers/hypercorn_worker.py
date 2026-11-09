import asyncio
import logging
from typing import Any

from temporal_boost.workers.asgi import ManagedAsgiWorker, load_asgi_app
from temporal_boost.workers.asgi_registry import ASGIWorkerType, asgi_worker_registry


@asgi_worker_registry.register(ASGIWorkerType.hypercorn.value, packages=["hypercorn"])
class HypercornBoostWorker(ManagedAsgiWorker):
    def __init__(
        self,
        app: Any,
        host: str,
        port: int,
        *,
        log_level: str | int | None = None,
        log_config: dict[str, Any] | None = None,
        **asgi_worker_kwargs: Any,
    ) -> None:
        super().__init__(
            app,
            host,
            port,
            log_level=log_level,
            log_config=log_config,
            **asgi_worker_kwargs,
        )
        self.name = "hypercorn"

    async def _serve(self, stop: asyncio.Event) -> None:
        try:
            from hypercorn.asyncio import serve  # type: ignore[import-not-found]  # noqa: PLC0415
            from hypercorn.config import Config  # type: ignore[import-not-found]  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("hypercorn is not installed. Install temporal-boost[hypercorn].") from exc

        options = self._asgi_worker_kwargs
        if options.get("workers", 1) != 1 or options.get("use_reloader", False):
            raise ValueError("Managed Hypercorn requires workers=1 and use_reloader=False")
        if options.get("worker_class", "asyncio") != "asyncio" or options.get("debug", False):
            raise ValueError("Managed Hypercorn supports worker_class='asyncio' and debug=False")

        config = Config()
        config.bind = [f"{self._host}:{self._port}"]
        if self._log_level is not None:
            config.loglevel = (
                logging.getLevelName(self._log_level) if isinstance(self._log_level, int) else self._log_level
            )

        config.logconfig_dict = self._log_config

        for key, value in options.items():
            if not hasattr(config, key) or callable(getattr(config, key)):
                raise ValueError(f"Unsupported Hypercorn configuration option: {key}")
            setattr(config, key, value)

        app = load_asgi_app(self._app)
        await serve(app, config, mode="asgi", shutdown_trigger=stop.wait)
