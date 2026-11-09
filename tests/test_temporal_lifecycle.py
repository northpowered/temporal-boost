import asyncio
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.client import Client
from temporalio.runtime import Runtime

from temporal_boost import BoostApp
from temporal_boost.workers.temporal import TemporalBoostWorker


WAIT_TIMEOUT = 2.0


async def activity() -> None:
    pass


async def cron_runner() -> None:
    pass


class SdkWorker:
    def __init__(self) -> None:
        self.ready = asyncio.Event()
        self.finish = asyncio.Event()
        self.finished = asyncio.Event()
        self.thread_ready = threading.Event()
        self.owner_loop: asyncio.AbstractEventLoop | None = None
        self.shutdown_calls = 0
        self.run_error: BaseException | None = None
        self.shutdown_error: BaseException | None = None

    async def run(self) -> None:
        self.owner_loop = asyncio.get_running_loop()
        try:
            if self.run_error is not None:
                raise self.run_error
            self.ready.set()
            self.thread_ready.set()
            await self.finish.wait()
        finally:
            self.finished.set()

    async def shutdown(self) -> None:
        self.shutdown_calls += 1
        assert asyncio.get_running_loop() is self.owner_loop
        if self.shutdown_error is not None:
            raise self.shutdown_error
        self.finish.set()
        await self.finished.wait()


@contextmanager
def resources() -> Iterator[tuple[TemporalBoostWorker, SdkWorker, MagicMock, MagicMock]]:
    worker = TemporalBoostWorker(
        "service", "queue", activities=[activity], cron_schedule="0 * * * *", cron_runner=cron_runner
    )
    sdk = SdkWorker()
    client = MagicMock(spec_set=Client)
    client.start_workflow = AsyncMock()
    runtime = MagicMock(spec_set=Runtime)
    with (
        patch("temporal_boost.temporal.runtime.Runtime", return_value=runtime),
        patch("temporalio.client.Client.connect", new=AsyncMock(return_value=client)),
        patch("temporal_boost.temporal.worker.Worker", return_value=sdk),
    ):
        yield worker, sdk, client, runtime


async def stop_and_wait(worker: TemporalBoostWorker, task: asyncio.Task[None]) -> None:
    worker.request_stop()
    await asyncio.wait_for(task, WAIT_TIMEOUT)


@pytest.mark.asyncio
async def test_shutdown_before_start_is_repeatable() -> None:
    with resources() as (worker, sdk, _, _):
        await worker.shutdown()
        await worker.shutdown()
        assert sdk.shutdown_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["runtime", "client", "worker"])
async def test_partial_startup_preserves_error_and_releases_references(stage: str) -> None:
    primary = RuntimeError(f"{stage} build failed")
    targets = {
        "runtime": "temporal_boost.temporal.runtime.Runtime",
        "client": "temporalio.client.Client.connect",
        "worker": "temporal_boost.temporal.worker.Worker",
    }
    with resources() as (worker, sdk, client, runtime):
        with patch(targets[stage], side_effect=primary):
            with pytest.raises(RuntimeError, match=f"{stage} build failed") as raised:
                await asyncio.wait_for(worker._run_worker(), WAIT_TIMEOUT)

        assert raised.value is primary
        assert worker._worker is None
        assert worker._client is None
        assert worker._runtime is None
        assert worker._worker_builder._client is None
        if worker._client_builder is not None:
            assert worker._client_builder._runtime is None
        assert sdk.shutdown_calls == 0
        assert not hasattr(client, "close")
        assert not hasattr(runtime, "close")
        await worker.shutdown()
        worker.configure_temporal_client(namespace="retry")
        worker.configure_temporal_runtime(metric_prefix="retry")


@pytest.mark.asyncio
@pytest.mark.parametrize("with_cron", [False, True])
async def test_repeated_shutdown_waits_for_run_and_stays_on_owner_loop(with_cron: bool) -> None:
    with resources() as (worker, sdk, client, _):
        task = asyncio.create_task(worker._run_with_cron() if with_cron else worker._run_worker())
        try:
            await asyncio.wait_for(sdk.ready.wait(), WAIT_TIMEOUT)
            await asyncio.wait_for(asyncio.gather(worker.shutdown(), worker.shutdown()), WAIT_TIMEOUT)
            await asyncio.wait_for(task, WAIT_TIMEOUT)
        finally:
            await stop_and_wait(worker, task)

        assert sdk.shutdown_calls == 1
        assert sdk.finished.is_set()
        assert sdk.owner_loop is asyncio.get_running_loop()
        assert worker._client is None
        assert worker._runtime is None
        await worker.shutdown()
        assert sdk.shutdown_calls == 1
        if with_cron:
            client.start_workflow.assert_awaited_once()
        else:
            client.start_workflow.assert_not_awaited()


@pytest.mark.asyncio
async def test_sdk_run_failure_does_not_wait_on_unstarted_sdk_shutdown() -> None:
    with resources() as (worker, sdk, _, _):
        primary = RuntimeError("SDK validation failed")
        sdk.run_error = primary
        with pytest.raises(RuntimeError, match="SDK validation failed") as raised:
            await asyncio.wait_for(worker._run_worker(), WAIT_TIMEOUT)

        assert raised.value is primary
        assert sdk.shutdown_calls == 0
        await worker.shutdown()


@pytest.mark.asyncio
async def test_cron_registration_error_survives_cleanup_failure(caplog: pytest.LogCaptureFixture) -> None:
    with resources() as (worker, sdk, client, _):
        primary = RuntimeError("CRON registration failed")
        client.start_workflow.side_effect = primary
        sdk.shutdown_error = ValueError("SDK cleanup failed")
        with pytest.raises(RuntimeError, match="CRON registration failed") as raised:
            await asyncio.wait_for(worker._run_with_cron(), WAIT_TIMEOUT)

        assert raised.value is primary
        assert sdk.shutdown_calls == 1
        assert sdk.finished.is_set()
        assert "SDK cleanup failed" in caplog.text
        assert worker._client is None
        assert worker._runtime is None


@pytest.mark.asyncio
async def test_stop_during_client_build_cancels_startup_and_skips_sdk() -> None:
    with resources() as (worker, sdk, _, _):
        building = asyncio.Event()
        cancelled = asyncio.Event()

        async def connect(**_kwargs: Any) -> None:
            building.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with patch("temporalio.client.Client.connect", side_effect=connect):
            task = asyncio.create_task(worker._run_worker())
            try:
                await asyncio.wait_for(building.wait(), WAIT_TIMEOUT)
                await asyncio.wait_for(worker.shutdown(), WAIT_TIMEOUT)
                await asyncio.wait_for(task, WAIT_TIMEOUT)
            finally:
                await stop_and_wait(worker, task)

        assert cancelled.is_set()
        assert sdk.shutdown_calls == 0
        assert not sdk.ready.is_set()
        assert worker._runtime is None


@pytest.mark.asyncio
async def test_stop_before_start_does_not_build_resources() -> None:
    with resources() as (worker, sdk, client, _):
        assert worker.request_stop()
        assert worker.request_stop()
        await asyncio.wait_for(worker._run_worker(), WAIT_TIMEOUT)
        assert not sdk.ready.is_set()
        client.start_workflow.assert_not_awaited()
        assert worker._client_builder is None


def assert_configuration_rejected(worker: TemporalBoostWorker) -> None:
    client_builder, runtime_builder = worker._client_builder, worker._runtime_builder
    client, sdk, runtime = worker._client, worker._worker, worker._runtime
    with pytest.raises(RuntimeError, match=r"configure.*client"):
        worker.configure_temporal_client(target_host="ignored:7233", namespace="ignored")
    with pytest.raises(RuntimeError, match=r"configure.*runtime"):
        worker.configure_temporal_runtime(metric_prefix="ignored")
    assert worker._client_builder is client_builder
    assert worker._runtime_builder is runtime_builder
    assert worker._client is client
    assert worker._worker is sdk
    assert worker._runtime is runtime


@pytest.mark.asyncio
async def test_configuration_is_rejected_while_building_running_and_stopping() -> None:
    connecting, connected = asyncio.Event(), asyncio.Event()
    stopping, stopped = asyncio.Event(), asyncio.Event()
    with resources() as (worker, sdk, client, _):

        async def connect(**_kwargs: Any) -> MagicMock:
            connecting.set()
            await connected.wait()
            return client

        original_shutdown = sdk.shutdown

        async def shutdown() -> None:
            stopping.set()
            await stopped.wait()
            await original_shutdown()

        with (
            patch("temporalio.client.Client.connect", side_effect=connect) as connect_mock,
            patch.object(sdk, "shutdown", side_effect=shutdown),
        ):
            task = asyncio.create_task(worker._run_worker())
            try:
                await asyncio.wait_for(connecting.wait(), WAIT_TIMEOUT)
                assert worker.state == "building"
                await asyncio.to_thread(assert_configuration_rejected, worker)
                connected.set()
                await asyncio.wait_for(sdk.ready.wait(), WAIT_TIMEOUT)
                assert worker.state == "running"
                assert_configuration_rejected(worker)
                worker.request_stop()
                await asyncio.wait_for(stopping.wait(), WAIT_TIMEOUT)
                assert worker.state == "stopping"
                assert_configuration_rejected(worker)
                connect_mock.assert_awaited_once()
            finally:
                connected.set()
                stopped.set()
                await stop_and_wait(worker, task)


@pytest.mark.asyncio
async def test_stopped_configuration_is_applied_on_next_run_with_fresh_objects() -> None:
    with resources() as (worker, sdk, client, runtime):
        task = asyncio.create_task(worker._run_worker())
        try:
            await asyncio.wait_for(sdk.ready.wait(), WAIT_TIMEOUT)
        finally:
            await stop_and_wait(worker, task)
        assert worker.state == "stopped"
        next_sdk, next_client, next_runtime = SdkWorker(), MagicMock(spec_set=Client), MagicMock(spec_set=Runtime)
        worker.configure_temporal_client(target_host="next:7233", namespace="next", tls=False)
        worker.configure_temporal_runtime(metric_prefix="next", prometheus_bind_address="127.0.0.1:9200")
        with (
            patch("temporal_boost.temporal.runtime.Runtime", return_value=next_runtime) as create_runtime,
            patch("temporalio.client.Client.connect", new=AsyncMock(return_value=next_client)) as connect,
            patch("temporal_boost.temporal.worker.Worker", return_value=next_sdk) as create_worker,
        ):
            task = asyncio.create_task(worker._run_worker())
            try:
                await asyncio.wait_for(next_sdk.ready.wait(), WAIT_TIMEOUT)
                assert worker.temporal_client_runtime is next_runtime
                assert worker.temporal_client is next_client
                assert worker.temporal_worker is next_sdk
                assert next_runtime is not runtime
                assert next_client is not client
                assert next_sdk is not sdk
                assert connect.call_args.kwargs["target_host"] == "next:7233"
                assert connect.call_args.kwargs["namespace"] == "next"
                assert connect.call_args.kwargs["runtime"] is next_runtime
                assert create_runtime.call_args.kwargs["telemetry"].metric_prefix == "next"
                assert create_runtime.call_args.kwargs["telemetry"].metrics.bind_address == "127.0.0.1:9200"
                assert create_worker.call_args.kwargs["client"] is next_client
            finally:
                await stop_and_wait(worker, task)
        assert worker.state == "stopped"


@pytest.mark.asyncio
async def test_state_transitions_and_cancelling_a_shutdown_waiter() -> None:
    with resources() as (worker, sdk, _, _):
        assert worker.state == "created"
        connecting, connected = asyncio.Event(), asyncio.Event()
        stopping, stopped = asyncio.Event(), asyncio.Event()

        async def connect(**_kwargs: Any) -> MagicMock:
            connecting.set()
            await connected.wait()
            return MagicMock(spec_set=Client)

        original_shutdown = sdk.shutdown

        async def shutdown() -> None:
            stopping.set()
            await stopped.wait()
            await original_shutdown()

        with (
            patch("temporalio.client.Client.connect", side_effect=connect),
            patch.object(sdk, "shutdown", side_effect=shutdown),
        ):
            task = asyncio.create_task(worker._run_worker())
            first_waiter: asyncio.Task[None] | None = None
            try:
                await asyncio.wait_for(connecting.wait(), WAIT_TIMEOUT)
                assert worker.state == "building"
                connected.set()
                await asyncio.wait_for(sdk.ready.wait(), WAIT_TIMEOUT)
                assert worker.state == "running"
                first_waiter = asyncio.create_task(worker.shutdown())
                await asyncio.wait_for(stopping.wait(), WAIT_TIMEOUT)
                assert worker.state == "stopping"
                first_waiter.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await first_waiter
                assert not task.done()
                assert worker._client is not None
                stopped.set()
                await asyncio.wait_for(worker.shutdown(), WAIT_TIMEOUT)
                await asyncio.wait_for(task, WAIT_TIMEOUT)
            finally:
                connected.set()
                stopped.set()
                await stop_and_wait(worker, task)
                if first_waiter is not None:
                    await asyncio.gather(first_waiter, return_exceptions=True)

        assert worker.state == "stopped"
        assert sdk.shutdown_calls == 1


@pytest.mark.asyncio
async def test_cron_stop_completes_waiter_and_cancels_pending_registration() -> None:
    with resources() as (worker, sdk, client, _):
        registering, cancelled = asyncio.Event(), asyncio.Event()

        async def register(*_args: Any, **_kwargs: Any) -> None:
            registering.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        client.start_workflow.side_effect = register
        task = asyncio.create_task(worker._run_with_cron())
        try:
            await asyncio.wait_for(registering.wait(), WAIT_TIMEOUT)
            cron_future = worker._cron_future
            assert cron_future is not None
            assert not cron_future.done()
            await asyncio.wait_for(worker.shutdown(), WAIT_TIMEOUT)
            await asyncio.wait_for(task, WAIT_TIMEOUT)
        finally:
            await stop_and_wait(worker, task)

        assert cron_future.done()
        assert cancelled.is_set()
        assert sdk.shutdown_calls == 1


@pytest.mark.asyncio
async def test_cron_stop_after_registration_completes_waiter() -> None:
    with resources() as (worker, sdk, client, _):
        registered = asyncio.Event()

        def register(*_args: Any, **_kwargs: Any) -> MagicMock:
            registered.set()
            return MagicMock(id=worker.cron_workflow_id, result_run_id="registered-run")

        client.start_workflow.side_effect = register
        task = asyncio.create_task(worker._run_with_cron())
        try:
            await asyncio.wait_for(registered.wait(), WAIT_TIMEOUT)
            cron_future = worker._cron_future
            assert cron_future is not None
            await asyncio.wait_for(worker.shutdown(), WAIT_TIMEOUT)
            await asyncio.wait_for(task, WAIT_TIMEOUT)
        finally:
            await stop_and_wait(worker, task)

        assert cron_future.done()
        assert sdk.shutdown_calls == 1
        client.start_workflow.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_consumer_and_cron_runs_are_rejected() -> None:
    with resources() as (worker, sdk, _, _):
        task = asyncio.create_task(worker._run_worker())
        try:
            await asyncio.wait_for(sdk.ready.wait(), WAIT_TIMEOUT)
            with pytest.raises(RuntimeError, match="already running"):
                await worker._run_with_cron()
        finally:
            await stop_and_wait(worker, task)


@pytest.mark.asyncio
async def test_unexpected_cancellation_propagates_after_sdk_cleanup() -> None:
    with resources() as (worker, sdk, _, _):
        task = asyncio.create_task(worker._run_worker())
        await asyncio.wait_for(sdk.ready.wait(), WAIT_TIMEOUT)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, WAIT_TIMEOUT)
        assert sdk.finished.is_set()
        assert sdk.shutdown_calls == 1
        assert worker.state == "stopped"


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["client", "worker"])
async def test_build_error_remains_primary_when_cleanup_fails(stage: str, caplog: pytest.LogCaptureFixture) -> None:
    with resources() as (worker, _, _, _):
        primary = RuntimeError("build failed")
        target = "temporalio.client.Client.connect" if stage == "client" else "temporal_boost.temporal.worker.Worker"
        original_cleanup = worker._cleanup

        async def cleanup(error: BaseException | None) -> None:
            await original_cleanup(error)
            raise ValueError("cleanup failed")

        with patch(target, side_effect=primary), patch.object(worker, "_cleanup", side_effect=cleanup):
            with pytest.raises(RuntimeError, match="build failed") as raised:
                await asyncio.wait_for(worker._run_worker(), WAIT_TIMEOUT)

        assert raised.value is primary
        assert "cleanup failed" in caplog.text
        assert worker._client is None
        assert worker._runtime is None


def test_application_coordinator_stops_temporal_on_its_own_loop() -> None:
    with resources() as (worker, sdk, _, _):
        app = BoostApp(logger_config=None)
        app.add_async_runtime(worker.name, worker)
        errors: list[BaseException] = []

        def run() -> None:
            try:
                app.run_all_workers()
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        try:
            assert sdk.thread_ready.wait(WAIT_TIMEOUT)
            app.stop()
            thread.join(WAIT_TIMEOUT)
            assert not thread.is_alive()
        finally:
            app.stop()
            worker.request_stop()
            thread.join(WAIT_TIMEOUT)

        assert errors == []
        assert sdk.shutdown_calls == 1
        assert sdk.finished.is_set()
        assert sdk.owner_loop is not None
        assert sdk.owner_loop.is_closed()
        assert worker.state == "stopped"


@pytest.mark.asyncio
async def test_shutdown_from_another_loop_rejects_foreign_cleanup() -> None:
    with resources() as (worker, sdk, _, _):
        task = asyncio.create_task(worker._run_worker())
        try:
            await asyncio.wait_for(sdk.ready.wait(), WAIT_TIMEOUT)

            def foreign_shutdown() -> None:
                asyncio.run(worker.shutdown())

            with pytest.raises(RuntimeError, match="request_stop"):
                await asyncio.to_thread(foreign_shutdown)
            assert not task.done()
            assert sdk.shutdown_calls == 0
        finally:
            await stop_and_wait(worker, task)


@pytest.mark.asyncio
async def test_sequential_runs_rebuild_resources_after_stop() -> None:
    with resources() as (worker, _, _, _):
        sdks = [SdkWorker(), SdkWorker()]
        clients = [MagicMock(spec_set=Client), MagicMock(spec_set=Client)]
        for client in clients:
            client.start_workflow = AsyncMock()
        runtimes = [MagicMock(spec_set=Runtime), MagicMock(spec_set=Runtime)]
        with (
            patch("temporal_boost.temporal.worker.Worker", side_effect=sdks) as make_sdk,
            patch("temporalio.client.Client.connect", side_effect=clients) as connect,
            patch("temporal_boost.temporal.runtime.Runtime", side_effect=runtimes) as make_runtime,
        ):
            for index, sdk in enumerate(sdks):
                task = asyncio.create_task(worker._run_worker() if index == 0 else worker._run_with_cron())
                try:
                    await asyncio.wait_for(sdk.ready.wait(), WAIT_TIMEOUT)
                    assert worker.temporal_client is clients[index]
                    assert worker.temporal_client_runtime is runtimes[index]
                    await asyncio.wait_for(worker.shutdown(), WAIT_TIMEOUT)
                    await asyncio.wait_for(task, WAIT_TIMEOUT)
                finally:
                    await stop_and_wait(worker, task)
                assert worker.state == "stopped"
                assert sdk.shutdown_calls == 1
                # A late request must not poison a subsequent run.
                assert worker.request_stop()

        assert make_sdk.call_count == 2
        assert connect.await_count == 2
        assert make_runtime.call_count == 2
        clients[0].start_workflow.assert_not_awaited()
        clients[1].start_workflow.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_sdk_validation_error_during_stop_does_not_hang_shutdown(
    cleanup_fails: bool, caplog: pytest.LogCaptureFixture
) -> None:
    with resources() as (worker, sdk, _, _):
        validating, fail_validation, shutting_down = asyncio.Event(), asyncio.Event(), asyncio.Event()
        primary = RuntimeError("validation failed while stopping")

        async def run() -> None:
            validating.set()
            await fail_validation.wait()
            raise primary

        async def shutdown() -> None:
            shutting_down.set()
            if cleanup_fails:
                await fail_validation.wait()
                raise ValueError("parallel SDK cleanup failed")
            await asyncio.Event().wait()

        with patch.object(sdk, "run", side_effect=run), patch.object(sdk, "shutdown", side_effect=shutdown) as stop:
            task = asyncio.create_task(worker._run_worker())
            try:
                await asyncio.wait_for(validating.wait(), WAIT_TIMEOUT)
                worker.request_stop()
                await asyncio.wait_for(shutting_down.wait(), WAIT_TIMEOUT)
                fail_validation.set()
                with pytest.raises(RuntimeError, match="validation failed while stopping") as raised:
                    await asyncio.wait_for(task, WAIT_TIMEOUT)
                assert raised.value is primary
            finally:
                fail_validation.set()
                worker.request_stop()
                await asyncio.gather(task, return_exceptions=True)

        stop.assert_awaited_once()
        assert worker.state == "stopped"
        if cleanup_fails:
            assert "parallel SDK cleanup failed" in caplog.text


@pytest.mark.asyncio
async def test_cleanup_error_propagates_on_requested_stop() -> None:
    with resources() as (worker, sdk, _, _):
        failure = ValueError("SDK shutdown failed")
        sdk.shutdown_error = failure
        task = asyncio.create_task(worker._run_worker())
        await asyncio.wait_for(sdk.ready.wait(), WAIT_TIMEOUT)
        worker.request_stop()
        with pytest.raises(ValueError, match="SDK shutdown failed") as raised:
            await asyncio.wait_for(task, WAIT_TIMEOUT)

        assert raised.value is failure
        assert sdk.finished.is_set()
        assert sdk.shutdown_calls == 1
        assert worker._worker is None
        assert worker._client is None
        assert worker._runtime is None
        await worker.shutdown()
