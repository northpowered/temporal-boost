"""Standalone runtime ownership: uv run python -m examples.example_runtime (Temporal required)."""

import asyncio

from temporalio import activity

from temporal_boost.temporal.client import TemporalClientBuilder
from temporal_boost.temporal.runtime import TemporalRuntimeBuilder
from temporal_boost.temporal.worker import TemporalWorkerBuilder


@activity.defn
async def greet(name: str) -> str:
    return f"Hello, {name}!"


async def run_worker() -> None:
    runtime = TemporalRuntimeBuilder(prometheus_bind_address="127.0.0.1:9090").build()
    client_builder = TemporalClientBuilder(target_host="localhost:7233", namespace="default")
    client_builder.set_runtime(runtime)
    client = await client_builder.build()
    worker_builder = TemporalWorkerBuilder(task_queue="custom_queue")
    worker_builder.set_client(client)
    worker_builder.set_activities([greet])
    worker = worker_builder.build()
    async with worker:
        # Keep serving until cancelled; the context shuts down the SDK worker.
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run_worker())
