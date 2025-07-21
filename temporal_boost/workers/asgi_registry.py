from collections.abc import Callable
from enum import Enum

from temporal_boost.workers.base import BaseAsgiWorker


class ASGIWorkerRegistry:
    def __init__(self) -> None:
        self._data: dict[str, type[BaseAsgiWorker]] = {}

    def register(
        self,
        key: str,
        packages: list[str] | None = None,
    ) -> Callable[[type[BaseAsgiWorker]], type[BaseAsgiWorker]]:
        if packages is None:
            packages = []

        def decorator(cls: type[BaseAsgiWorker]) -> type[BaseAsgiWorker]:
            try:
                for package in packages:
                    __import__(package)
            except ImportError:
                return cls
            self._data[key] = cls
            return cls

        return decorator

    def get(self, key: str) -> type[BaseAsgiWorker]:
        try:
            return self._data[key]
        except KeyError:
            raise RuntimeError(f"Worker implementation '{key}' is not available.") from None

    def available_keys(self) -> list[str]:
        return list(self._data.keys())


asgi_worker_registry = ASGIWorkerRegistry()


class ASGIWorkerType(str, Enum):
    uvicorn = "uvicorn"
    hypercorn = "hypercorn"
    granian = "granian"
    auto = "auto"


def get_asgi_worker_class(worker_type: ASGIWorkerType) -> type[BaseAsgiWorker]:
    if worker_type == ASGIWorkerType.auto:
        if ASGIWorkerType.uvicorn.value in asgi_worker_registry.available_keys():
            return asgi_worker_registry.get(ASGIWorkerType.uvicorn.value)

        available = asgi_worker_registry.available_keys()
        if not available:
            raise RuntimeError("No ASGI worker implementation is available.")
        return asgi_worker_registry.get(available[0])
    return asgi_worker_registry.get(worker_type.value)
