import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio import workflow
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from temporal_boost import BoostApp
from temporal_boost.workers.temporal import TemporalBoostWorker


@workflow.defn(sandboxed=False)
class CronProbe:
    @workflow.run
    async def run(self) -> str:
        return "done"


def make_worker(
    worker_name: str = "daily_report",
    task_queue: str = "report_queue",
    cron_workflow_id: str | None = None,
) -> TemporalBoostWorker:
    return TemporalBoostWorker(
        worker_name,
        task_queue,
        workflows=[CronProbe],
        cron_schedule="0 0 * * *",
        cron_runner=CronProbe.run,
        cron_workflow_id=cron_workflow_id,
    )


def test_default_identity_is_stable_and_scoped_to_queue_and_worker() -> None:
    worker = make_worker()
    assert worker.cron_workflow_id == "temporal-boost/cron/report_queue/daily_report"
    assert make_worker().cron_workflow_id == worker.cron_workflow_id
    assert make_worker(task_queue="other").cron_workflow_id != worker.cron_workflow_id
    assert make_worker(worker_name="other").cron_workflow_id != worker.cron_workflow_id
    assert make_worker("b/c", "a").cron_workflow_id != make_worker("c", "a/b").cron_workflow_id
    assert make_worker("b%2Fc", "a").cron_workflow_id != make_worker("b/c", "a").cron_workflow_id


@pytest.mark.parametrize("workflow_id", ["reports/daily-v1", "old-uuid", " preserved "])
def test_explicit_identity_is_preserved_across_queue_and_worker_changes(workflow_id: str) -> None:
    assert make_worker(cron_workflow_id=workflow_id).cron_workflow_id == workflow_id
    assert make_worker("renamed", "moved", workflow_id).cron_workflow_id == workflow_id


@pytest.mark.parametrize("workflow_id", ["", " ", "\t\n"])
def test_empty_explicit_identity_is_rejected(workflow_id: str) -> None:
    with pytest.raises(ValueError, match="cron_workflow_id must not be empty"):
        make_worker(cron_workflow_id=workflow_id)


def test_app_forwards_identity_without_leaking_it_to_sdk_worker() -> None:
    app = BoostApp(logger_config=None)
    with patch("temporal_boost.workers.temporal.TemporalWorkerBuilder", autospec=True) as builder:
        worker = app.add_worker(
            "daily_report",
            "report_queue",
            workflows=[CronProbe],
            cron_schedule="0 0 * * *",
            cron_runner=CronProbe.run,
            cron_workflow_id="reports/daily-v1",
        )
    assert worker.cron_workflow_id == "reports/daily-v1"
    assert "cron_workflow_id" not in builder.call_args.kwargs


@pytest.mark.asyncio
async def test_registration_reuses_active_id_with_explicit_server_policies(caplog: pytest.LogCaptureFixture) -> None:
    worker = make_worker()
    handle = MagicMock(id=worker.cron_workflow_id, result_run_id="existing-run")
    worker._client = MagicMock(namespace="test-namespace", start_workflow=AsyncMock(return_value=handle))

    with caplog.at_level(logging.INFO):
        assert await worker._register_cron() is handle
        assert await worker._register_cron() is handle

    assert worker._client.start_workflow.await_count == 2
    for call in worker._client.start_workflow.call_args_list:
        assert call.args == (CronProbe.run,)
        assert call.kwargs == {
            "id": worker.cron_workflow_id,
            "task_queue": "report_queue",
            "cron_schedule": "0 0 * * *",
            "id_conflict_policy": WorkflowIDConflictPolicy.USE_EXISTING,
            "id_reuse_policy": WorkflowIDReusePolicy.REJECT_DUPLICATE,
        }
    assert worker.cron_workflow_id in caplog.text
    assert "existing-run" in caplog.text
    assert "test-namespace" in caplog.text


@pytest.mark.asyncio
async def test_closed_identity_error_propagates_without_retry_or_new_id() -> None:
    worker = make_worker()
    error = WorkflowAlreadyStartedError(worker.cron_workflow_id, "CronProbe", run_id="closed-run")
    worker._client = MagicMock(start_workflow=AsyncMock(side_effect=error))

    with pytest.raises(WorkflowAlreadyStartedError) as raised:
        await worker._register_cron()

    assert raised.value is error
    worker._client.start_workflow.assert_awaited_once()


@pytest.mark.asyncio
async def test_cron_path_registers_and_local_cancellation_does_not_cancel_server_workflow() -> None:
    worker = make_worker()
    finished = asyncio.Event()
    sdk = MagicMock(run=AsyncMock(side_effect=finished.wait), shutdown=AsyncMock(side_effect=finished.set))
    client = MagicMock(start_workflow=AsyncMock())
    registered = asyncio.Event()

    async def build() -> None:
        worker._worker = sdk
        worker._client = client

    async def register() -> None:
        await TemporalBoostWorker._register_cron(worker)
        registered.set()

    with (
        patch.object(worker, "_build_worker", side_effect=build),
        patch.object(worker, "_register_cron", side_effect=register),
    ):
        task = asyncio.create_task(worker._run_with_cron())
        await asyncio.wait_for(registered.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    client.start_workflow.assert_awaited_once()
    client.start_workflow.return_value.cancel.assert_not_called()
    client.start_workflow.return_value.terminate.assert_not_called()
    sdk.shutdown.assert_awaited_once()
    assert worker.state == "stopped"
