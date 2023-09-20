# Import `BoostApp` class
from temporal_boost import BoostApp, BoostLoggerConfig

from temporalio import activity
from temporalio import workflow


# Create `BoostApp` object
app = BoostApp(
    logger_config=BoostLoggerConfig(
        json=False
    )
)


# Describe your activities/workflows
@activity.defn(name="test_boost_activity_1")
async def test_boost_activity_1(foo: str, bar: str) -> str:
    app.logger.info("This is built-in logger")
    return f"1_{foo}{bar}"


@activity.defn(name="test_boost_activity_2")
async def test_boost_activity_2(foo: str, bar: str) -> str:
    return f"2_{foo}{bar}"


@workflow.defn(name="TestCronWorkflow", sandboxed=False)
class TestCronWorkflow:
    @workflow.run
    async def run(self) -> None:
        print("With is cron workflow")
        return None


# Add async workers to your app

app.add_worker("worker_1", "task_q_1", activities=[test_boost_activity_1], metrics_endpoint="0.0.0.0:9000")
app.add_worker("worker_2", "task_q_2", activities=[test_boost_activity_2])
# Example of CRON worker
app.add_worker(
    "test_cron",
    "task_q_3",
    workflows=[TestCronWorkflow],
    cron_schedule="* * * * *",
    cron_runner=TestCronWorkflow.run
)

# Run your app and start workers with CLI
app.run()
