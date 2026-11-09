"""
CRON worker example for Temporal-boost.

This example demonstrates:
- Creating a CRON worker that runs on a schedule
- Scheduled workflow execution
- Daily report generation

Register or reuse the server-side CRON chain and consume its queue:
    uv run python examples/example_cron.py cron daily_report

Consume the queue without creating a schedule (for an existing chain):
    uv run python examples/example_cron.py run daily_report

Run every registered consumer without creating schedules:
    uv run python examples/example_cron.py run all
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from temporalio import activity, workflow

from temporal_boost import BoostApp


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BoostApp(name="cron-example")


@activity.defn(name="generate_report")
async def generate_report() -> dict[str, Any]:
    """Generate a daily report."""
    logger.info("Generating daily report...")
    # Simulate report generation
    now = datetime.now(tz=timezone.utc)
    return {
        "report_id": f"report_{now.date()}",
        "generated_at": now.isoformat(),
        "status": "completed",
    }


@workflow.defn(sandboxed=False, name="DailyReportWorkflow")
class DailyReportWorkflow:
    """Workflow that generates a daily report."""

    @workflow.run
    async def run(self) -> None:
        """Generate daily report."""
        logger.info("Starting daily report workflow")

        result = await workflow.execute_activity(
            generate_report,
            task_queue="report_queue",
            start_to_close_timeout=timedelta(minutes=30),
        )

        logger.info(f"Daily report generated: {result['report_id']}")


# Configure the CRON worker locally. Only the `cron daily_report` command
# registers the server-side chain; `run daily_report` and `run all` only consume.
app.add_worker(
    "daily_report",
    "report_queue",
    activities=[generate_report],
    workflows=[DailyReportWorkflow],
    cron_schedule="0 0 * * *",  # Every day at midnight
    cron_runner=DailyReportWorkflow.run,
    cron_workflow_id="reports/daily-v1",  # Keep identical across replicas and restarts
)

# Stopping this consumer leaves the server-side CRON chain running. Restarting
# with `cron daily_report` reuses it; changing this ID creates a separate job. See the migration guide
# before upgrading deployments that previously registered random UUID IDs.

if __name__ == "__main__":
    app.run()
