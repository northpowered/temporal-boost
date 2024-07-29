"""
For development purposes
"""

# Import `BoostApp` class
from temporal_boost import BoostApp, BoostLoggerConfig
from temporalio import activity
from temporalio import workflow
from datetime import timedelta
from dataclasses import dataclass

from example_asgi_app import fastapi_app

# Create `BoostApp` object
app: BoostApp = BoostApp(
    logger_config=BoostLoggerConfig(json=True, bind_extra={"app": "my", "ww": "xx"}),
    use_pydantic=True,
)


@dataclass
class TestModel:
    foo: str
    bar: int


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


@workflow.defn(sandboxed=False)
class MyWorkflow:
    @workflow.run
    async def run(self, foo: str):
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


# Add async workers to your app

app.add_worker(
    "worker_1",
    "task_q_1",
    activities=[test_boost_activity_1],
    metrics_endpoint="0.0.0.0:9000",
)
app.add_worker("worker_2", "task_q_2", activities=[test_boost_activity_2])

app.add_worker("worker_3", "task_q_3", workflows=[MyWorkflow])

# app.add_http_worker("test_http_worker_!", "0.0.0.0", 8000, routes=[])

app.add_asgi_worker("asgi_worker", fastapi_app, "0.0.0.0", 8000)

app.add_internal_worker("0.0.0.0", 8888)

# Run your app and start workers with CLI
app.run()
