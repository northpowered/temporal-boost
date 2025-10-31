"""
CRON worker example for Temporal-boost.

This example demonstrates:
- Creating a CRON worker that runs on a schedule
- Scheduled workflow execution
- Daily report generation

Run with: python3 example_cron.py cron daily_report
"""

import logging
from datetime import timedelta
from temporalio import activity, workflow
from temporal_boost import BoostApp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BoostApp(name="cron-example")

@activity.defn(name="generate_report")
async def generate_report() -> dict:
    """Generate a daily report."""
    logger.info("Generating daily report...")
    # Simulate report generation
    import datetime
    return {
        "report_id": f"report_{datetime.date.today()}",
        "generated_at": datetime.datetime.now().isoformat(),
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

# Register CRON worker - runs daily at midnight
app.add_worker(
    "daily_report",
    "report_queue",
    activities=[generate_report],
    workflows=[DailyReportWorkflow],
    cron_schedule="0 0 * * *",  # Every day at midnight
    cron_runner=DailyReportWorkflow.run,
)

if __name__ == "__main__":
    app.run()

