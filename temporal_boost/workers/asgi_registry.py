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
            existing = self._data.get(key)
            if existing is not None and existing is not cls:
                raise ValueError(f"ASGI worker implementation {key!r} is already registered")
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


# Preserve the historical effective order, independently of module import order.
ASGI_AUTO_PRIORITY = ("uvicorn", "granian", "hypercorn")


def get_asgi_worker_class(worker_type: ASGIWorkerType) -> type[BaseAsgiWorker]:
    if worker_type == ASGIWorkerType.auto:
        available = set(asgi_worker_registry.available_keys())
        for key in ASGI_AUTO_PRIORITY:
            if key in available:
                return asgi_worker_registry.get(key)
        if not available:
            raise RuntimeError("No ASGI worker implementation is available.")
        # Custom backends have a stable, lexical fallback after all built-ins.
        return asgi_worker_registry.get(min(available))
    return asgi_worker_registry.get(worker_type.value)
