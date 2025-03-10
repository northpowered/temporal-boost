"""
For development purposes
"""

# Import `BoostApp` class
import asyncio
import contextlib
import random
from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow

from examples.example_asgi_app import fastapi_app
from temporal_boost import BoostApp, BoostLoggerConfig, BoostOTLPConfig

# Create `BoostApp` object
app: BoostApp = BoostApp(
    logger_config=BoostLoggerConfig(json=True, bind_extra={"app": "my", "ww": "xx"}, level="DEBUG", multiprocess_safe=True),
    use_pydantic=True,
    name="BoostApp example",
    temporal_endpoint="localhost:7233",
    temporal_namespace="default",
    otlp_config=BoostOTLPConfig(otlp_endpoint="otlp-collector", service_name="example-app"),
)


@dataclass
class TestModel:
    foo: str
    bar: int
    spam: int = 3
    eggs: bool | None = None


def fake_db_migration():
    """
    Fake fn for db migrations
    """
    print("fake")


# Describe your activities/workflows
@activity.defn(name="test_boost_activity_1")
async def test_boost_activity_1(payload: TestModel) -> TestModel:
    payload.foo = f"{payload.foo}+activity1"
    payload.bar = payload.bar + 1
    return payload


@activity.defn(name="test_boost_activity_2")
async def test_boost_activity_2(payload: TestModel) -> TestModel:
    payload.foo = f"{payload.foo}+activity2"
    payload.bar = payload.bar + 1
    return payload


@activity.defn(name="custom_test_boost_activity_3")
async def test_boost_activity_3(payload: TestModel, foo: str, bar: int) -> TestModel:
    payload.foo = f"{payload.foo}+activity2"
    payload.bar = payload.bar + 1
    return payload


@workflow.defn(sandboxed=False, name="MyCustomFlowName")
class MyWorkflow:
    """
    Example doc for workflow
    """

    @workflow.run
    async def run(self, foo: str) -> TestModel:
        app.logger.info("Sync logger")
        with contextlib.suppress(TypeError):
            await app.logger.info("Async logger")
        start_payload: TestModel = TestModel(foo="hello", bar=0)
        print(type(start_payload))
        result_1 = await workflow.execute_activity(
            test_boost_activity_1,
            start_payload,
            task_queue="task_q_1",
            start_to_close_timeout=timedelta(minutes=1),
        )
        print(type(result_1))
        result_2 = await workflow.execute_activity(
            test_boost_activity_2,
            result_1,
            task_queue="task_q_2",
            start_to_close_timeout=timedelta(minutes=1),
        )
        print(type(result_2))
        return result_2

    @workflow.signal(name="my_custom_signal_name")
    async def my_signal(self, signal_arg: TestModel):
        print(signal_arg)


class TestAsyncRuntime:
    """
    Class must implement `run` method
    """

    async def _test_async_runtime(self):
        while True:
            print(random.random())
            await asyncio.sleep(1)

    def run(self):
        asyncio.run(self._test_async_runtime())


# Add async workers to your app
if __name__ == "__main__":
    app.add_worker(
        "worker_1",
        "task_q_1",
        activities=[test_boost_activity_1, test_boost_activity_3],
        metrics_endpoint="0.0.0.0:9000",
        description="This workers serves activity test_boost_activity_1 on task_q_1 queue",
    )
    app.add_worker("worker_2", "task_q_2", activities=[test_boost_activity_2])

    app.add_worker("worker_3", "task_q_3", workflows=[MyWorkflow])

    # app.add_worker("worker_4", "task_q_4", workflows=[MyWorkflow], cron_runner=MyWorkflow.run, cron_schedule="* * * * *")

    app.add_asgi_worker("asgi_worker", fastapi_app, "0.0.0.0", 8001)
    """
        Internal worker is not supported for Pyhton3.13 yet
        To use it, install `robyn` first
    """
    # app.add_internal_worker("0.0.0.0", 8998, doc_endpoint="/doc")

    app.add_exec_method_sync("migrate_db", fake_db_migration)

    # app.add_async_runtime("test_async", runtime=TestAsyncRuntime())
    # Run your app and start workers with CLI
    app.run()
