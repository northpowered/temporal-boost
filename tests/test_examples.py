import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from examples.example_custom_worker import ServiceWorker, create_app
from temporal_boost import BaseBoostWorker


@pytest.mark.asyncio
async def test_documented_runtime_is_attached_before_connecting() -> None:
    guide = await asyncio.to_thread(Path("docs/en/advanced_usage.md").read_text, encoding="utf-8")
    section = guide.split("Use builders directly", 1)[1]
    fragment = section.split("```python\n", 1)[1].split("\n```", 1)[0]
    namespace = {"__name__": "documented_runtime"}
    exec(compile(fragment, "advanced_usage.md", "exec"), namespace)  # noqa: S102 - execute the repository guide
    runtime = MagicMock()
    client = MagicMock()
    sdk_worker = MagicMock()
    sdk_worker.__aenter__ = AsyncMock()
    sdk_worker.__aexit__ = AsyncMock(return_value=False)
    with (
        patch("temporal_boost.temporal.runtime.Runtime", return_value=runtime),
        patch("temporal_boost.temporal.client.Client.connect", new_callable=AsyncMock, return_value=client) as connect,
        patch("temporal_boost.temporal.worker.Worker", return_value=sdk_worker) as worker,
        patch("asyncio.Event.wait", new_callable=AsyncMock, side_effect=asyncio.CancelledError),
    ):
        with pytest.raises(asyncio.CancelledError):
            await namespace["run_worker"]()
    assert connect.await_args.kwargs["runtime"] is runtime
    assert worker.call_args.kwargs["client"] is client
    assert worker.call_args.kwargs["activities"] == [namespace["greet"]]
    sdk_worker.__aenter__.assert_awaited_once()
    sdk_worker.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_standalone_custom_worker_stops_without_external_services() -> None:
    app = create_app()
    worker = next(worker for worker in app.get_registered_workers() if worker.name == "service")
    assert isinstance(worker, BaseBoostWorker)
    assert isinstance(worker, ServiceWorker)
    assert worker.name == "service"
    task = asyncio.create_task(worker.run_async())
    await asyncio.sleep(0)
    assert not task.done()
    await worker.shutdown()
    await asyncio.wait_for(task, timeout=1)
    assert worker.finished.is_set()


@pytest.mark.asyncio
async def test_comprehensive_custom_worker_is_registered_and_can_stop() -> None:
    pytest.importorskip("hypercorn")
    from examples.example_app import TestAsyncRuntime, app  # noqa: PLC0415 - optional example dependency

    worker = next(worker for worker in app.get_registered_workers() if worker.name == "custom_runtime")
    assert isinstance(worker, TestAsyncRuntime)
    task = asyncio.create_task(worker.run_async())
    await asyncio.sleep(0)
    await worker.shutdown()
    await asyncio.wait_for(task, timeout=1)
    assert worker.finished.is_set()
