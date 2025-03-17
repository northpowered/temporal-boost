import asyncio
import os
import sys
from collections.abc import Callable, Iterable
from enum import Enum
from typing import Any, Generic, TypeVar


WrappableT = Callable[..., Any]
LoopBuilderT = Callable[..., asyncio.AbstractEventLoop]


T = TypeVar("T")


class Loops(str, Enum):
    auto = "auto"
    asyncio = "asyncio"
    uvloop = "uvloop"


class BaseRegistry(Generic[T]):
    __slots__ = ["_data"]

    def __init__(self) -> None:
        self._data: dict[str, T] = {}

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def keys(self) -> Iterable[str]:
        return self._data.keys()


class FunctionRegistry(BaseRegistry[WrappableT]):
    def register(self, key: str) -> Callable[[WrappableT], WrappableT]:
        def wrap(builder: WrappableT) -> WrappableT:
            self._data[key] = builder
            return builder

        return wrap

    def get(self, key: str) -> WrappableT:
        try:
            return self._data[key]
        except KeyError:
            raise RuntimeError(f"'{key}' implementation not available.") from None


class BuilderRegistry(BaseRegistry[tuple[LoopBuilderT, dict[str, Any]]]):
    def register(self, key: str, packages: list[str] | None = None) -> Callable[[LoopBuilderT], LoopBuilderT]:
        if packages is None:
            packages = []

        def wrap(builder: LoopBuilderT) -> LoopBuilderT:
            loaded_packages: dict[str, Any] = {}
            implemented = True
            try:
                for package in packages:
                    __import__(package)
                    loaded_packages[package] = sys.modules[package]
            except ImportError:
                implemented = False
            if implemented:
                self._data[key] = (builder, loaded_packages)
            return builder

        return wrap

    def get(self, key: str) -> asyncio.AbstractEventLoop:
        try:
            builder, packages = self._data[key]
        except KeyError:
            raise RuntimeError(f"'{key}' implementation not available.") from None
        return builder(**packages)


loops = BuilderRegistry()


@loops.register("asyncio")
def build_asyncio_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.new_event_loop() if os.name != "nt" else asyncio.ProactorEventLoop()  # type:ignore[attr-defined]
    asyncio.set_event_loop(loop)
    return loop


@loops.register("uvloop", packages=["uvloop"])
def build_uv_loop(uvloop: Any) -> Any:
    uvloop.install()
    return uvloop.new_event_loop()


@loops.register("auto")
def build_auto_loop() -> asyncio.AbstractEventLoop:
    if "uvloop" in loops:
        return loops.get("uvloop")
    return loops.get("asyncio")
