"""Real-server checks: TEMPORAL_BOOST_INTEGRATION=1 uv run pytest tests/test_cron_integration.py.

The SDK downloads a Temporal CLI dev server unless TEMPORAL_CLI_PATH is set.
All workflows belong to this ephemeral server; no external namespace is used.
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest
from temporalio.client import WorkflowExecutionStatus
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from tests.test_cron_workflow_idempotency import CronProbe, make_worker


pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("TEMPORAL_BOOST_INTEGRATION") != "1", reason="requires opt-in real Temporal dev server"
    ),
]

# Separate interpreters have no shared lock or application state. Only the server
# can serialize their registration of the same logical CRON job.
REGISTER_IN_PROCESS = """
import asyncio
import sys
sys.path.insert(0, sys.argv[1])
from temporalio.client import Client
from tests.test_cron_workflow_idempotency import make_worker

async def main():
    worker = make_worker(task_queue=sys.argv[3])
    worker._client = await Client.connect(sys.argv[2])
    handle = await worker._register_cron()
    print(handle.result_run_id)

asyncio.run(main())
"""


async def test_restarts_and_process_race_share_one_chain_and_closed_ids_are_rejected() -> None:
    async with await WorkflowEnvironment.start_local(
        ip="127.0.0.1",
        dev_server_existing_path=os.getenv("TEMPORAL_CLI_PATH"),
        dev_server_log_level="error",
    ) as env:
        queue = f"cron-idempotency-{uuid.uuid4()}"
        target = env.client.service_client.config.target_host

        async def register_in_process() -> str:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                REGISTER_IN_PROCESS,
                str(Path(__file__).resolve().parent.parent),
                target,
                queue,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            assert process.returncode == 0, stderr.decode()
            return stdout.decode().strip()

        first_run, racing_run = await asyncio.gather(register_in_process(), register_in_process())
        assert first_run
        assert first_run == racing_run
        assert await register_in_process() == first_run

        worker = make_worker(task_queue=queue)
        worker._client = env.client
        handle = await worker._register_cron()
        assert handle.result_run_id == first_run
        description = await handle.describe()
        assert description.status == WorkflowExecutionStatus.RUNNING
        await handle.terminate(reason="test closed CRON ID policy")
        with pytest.raises(WorkflowAlreadyStartedError):
            await worker._register_cron()

        # A normally completed workflow must also remain closed on registration.
        completed_id = f"completed-{uuid.uuid4()}"
        async with Worker(env.client, task_queue=queue, workflows=[CronProbe]):
            assert await env.client.execute_workflow(CronProbe.run, id=completed_id, task_queue=queue) == "done"
        completed = make_worker(task_queue=queue, cron_workflow_id=completed_id)
        completed._client = env.client
        with pytest.raises(WorkflowAlreadyStartedError):
            await completed._register_cron()
