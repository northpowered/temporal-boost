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
        **kwargs: Any,
    ) -> None:
        pass
