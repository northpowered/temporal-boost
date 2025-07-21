from abc import ABC, abstractmethod
from typing import Any


class BaseBoostWorker(ABC):
    name: str

    @abstractmethod
    def run(self) -> None:
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        pass


class BaseAsgiWorker(BaseBoostWorker):
    def __init__(
        self,
        app: Any,
        host: str,
        port: int,
        *,
        log_level: str | int | None = None,
        log_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.name: str = ""  # Will be set by BoostApp
        self._app = app
        self._host = host
        self._port = port
        self._log_level = log_level
        self._log_config = log_config
        self._asgi_worker_kwargs = kwargs

    @abstractmethod
    def run(self) -> None:
        """Run the ASGI server. Must be implemented by subclasses."""

    async def shutdown(self) -> None:
        """Default shutdown implementation for ASGI workers."""
