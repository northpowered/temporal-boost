import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow

from temporal_boost import ASGIWorkerType, BaseBoostWorker, BoostApp


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = BoostApp(
    name="BoostApp example",
    temporal_endpoint="localhost:7233",
    temporal_namespace="default",
    use_pydantic=True,
)


@dataclass
class TestModel:
    foo: str
    bar: int
    spam: int = 3
    eggs: bool | None = None


def fake_db_migration() -> None:
    """Fake fn for db migrations."""


@activity.defn(name="test_boost_activity_1")
async def test_boost_activity_1(payload: TestModel) -> TestModel:  # noqa: RUF029
    payload.foo = f"{payload.foo}+activity1"
    payload.bar += 1
    return payload


@activity.defn(name="test_boost_activity_2")
async def test_boost_activity_2(payload: TestModel) -> TestModel:  # noqa: RUF029
    payload.foo = f"{payload.foo}+activity2"
    payload.bar += 1
    return payload


@activity.defn(name="custom_test_boost_activity_3")
async def test_boost_activity_3(payload: TestModel, foo: str, bar: int) -> TestModel:  # noqa: RUF029
    payload.foo = f"{payload.foo}+activity2"
    payload.bar += 1
    return payload


@workflow.defn(sandboxed=False, name="MyCustomFlowName")
class MyWorkflow:
    @workflow.run
    async def run(self, foo: str) -> TestModel:  # noqa: ARG002
        logger.info("Sync logger")

        start_payload: TestModel = TestModel(foo="hello", bar=0)
        result_1 = await workflow.execute_activity(
            test_boost_activity_1,
            start_payload,
            task_queue="task_q_1",
            start_to_close_timeout=timedelta(minutes=1),
        )
        return await workflow.execute_activity(
            test_boost_activity_2,
            result_1,
            task_queue="task_q_2",
            start_to_close_timeout=timedelta(minutes=1),
        )

    @workflow.signal(name="my_custom_signal_name")
    async def my_signal(self, signal_arg: TestModel) -> None:
        pass


class TestAsyncRuntime(BaseBoostWorker):
    async def _test_async_runtime(self) -> None:
        while True:  # noqa: ASYNC110
            await asyncio.sleep(1)

    def run(self) -> None:
        asyncio.run(self._test_async_runtime())


app.add_worker(
    "worker_1",
    "task_q_1",
    activities=[test_boost_activity_1, test_boost_activity_3],
)
app.add_worker("worker_2", "task_q_2", activities=[test_boost_activity_2])
boost_worker = app.add_worker("worker_3", "task_q_3", workflows=[MyWorkflow])
boost_worker.configure_temporal_client(use_pydantic_data_converter=True)
boost_worker.configure_temporal_runtime(prometheus_bind_address="0.0.0.0:8801")

app.add_asgi_worker(
    "asgi_worker",
    "examples.example_asgi_app:fastapi_app",
    "0.0.0.0",
    8001,
    asgi_worker_type=ASGIWorkerType.hypercorn,
)
app.add_exec_method_sync("migrate_db", fake_db_migration)

app.run()
