from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar

import typer

from temporal_boost.workers.base import BaseAsgiWorker, BaseBoostWorker


_process_count: ContextVar[int] = ContextVar("external_process_count", default=1)


def validate_asgi_processes(workers: Sequence[BaseBoostWorker]) -> None:
    """Reject replicated ASGI commands before they start any workers.

    Raises:
        typer.BadParameter: If an external multiprocess command selects ASGI workers.
    """
    if _process_count.get() <= 1:
        return
    asgi_names = [worker.name for worker in workers if isinstance(worker, BaseAsgiWorker)]
    if asgi_names:
        raise typer.BadParameter(
            f"Cannot launch ASGI workers ({', '.join(asgi_names)}) with --workers > 1: "
            "the external launcher does not share listening sockets. "
            "Use --workers 1 for HTTP and scale Temporal consumers separately with run <consumer-name>."
        )


@contextmanager
def multiprocess_execution(count: int) -> Iterator[None]:
    """Scope the external launcher's process count to a child CLI invocation."""
    token = _process_count.set(count)
    try:
        yield
    finally:
        _process_count.reset(token)
