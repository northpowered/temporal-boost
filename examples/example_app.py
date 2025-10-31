"""
Comprehensive example demonstrating various Temporal-boost features.

This example demonstrates:
- Multiple workers with different configurations
- Pydantic models for type safety
- Workflow signals
- ASGI worker integration
- Custom worker configuration
- Prometheus metrics
- Custom exec methods

Run with: python3 example_app.py run all
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow

from temporal_boost import ASGIWorkerType, BaseBoostWorker, BoostApp

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize application
app = BoostApp(
    name="comprehensive-example",
    temporal_endpoint="localhost:7233",
    temporal_namespace="default",
    use_pydantic=True,
)

# Data model
@dataclass
class TestModel:
    """Test data model."""
    foo: str
    bar: int
    spam: int = 3
    eggs: bool | None = None

# Custom exec method
def fake_db_migration() -> None:
    """Fake database migration function."""
    logger.info("Running database migration...")

# Activities
@activity.defn(name="test_boost_activity_1")
async def test_boost_activity_1(payload: TestModel) -> TestModel:  # noqa: RUF029
    """First activity that processes payload."""
    logger.info(f"Activity 1 processing: {payload.foo}")
    payload.foo = f"{payload.foo}+activity1"
    payload.bar += 1
    return payload

@activity.defn(name="test_boost_activity_2")
async def test_boost_activity_2(payload: TestModel) -> TestModel:  # noqa: RUF029
    """Second activity that processes payload."""
    logger.info(f"Activity 2 processing: {payload.foo}")
    payload.foo = f"{payload.foo}+activity2"
    payload.bar += 1
    return payload

@activity.defn(name="custom_test_boost_activity_3")
async def test_boost_activity_3(payload: TestModel, foo: str, bar: int) -> TestModel:  # noqa: RUF029
    """Third activity with additional parameters."""
    logger.info(f"Activity 3 processing: {payload.foo} with {foo} and {bar}")
    payload.foo = f"{payload.foo}+activity3"
    payload.bar += 1
    return payload

# Workflow
@workflow.defn(sandboxed=False, name="MyCustomFlowName")
class MyWorkflow:
    """Example workflow with signals."""
    
    def __init__(self):
        self.signal_data: TestModel | None = None

    @workflow.run
    async def run(self, foo: str) -> TestModel:  # noqa: ARG002
        """Main workflow execution."""
        logger.info("Starting workflow")

        start_payload: TestModel = TestModel(foo="hello", bar=0)
        
        # Execute first activity
        result_1 = await workflow.execute_activity(
            test_boost_activity_1,
            start_payload,
            task_queue="task_q_1",
            start_to_close_timeout=timedelta(minutes=1),
        )
        
        # Execute second activity
        result_2 = await workflow.execute_activity(
            test_boost_activity_2,
            result_1,
            task_queue="task_q_2",
            start_to_close_timeout=timedelta(minutes=1),
        )
        
        return result_2

    @workflow.signal(name="my_custom_signal_name")
    async def my_signal(self, signal_arg: TestModel) -> None:
        """Signal handler for custom signal."""
        logger.info(f"Received signal: {signal_arg}")
        self.signal_data = signal_arg

# Custom async runtime worker
class TestAsyncRuntime(BaseBoostWorker):
    """Custom worker with async runtime."""
    
    async def _test_async_runtime(self) -> None:
        """Async runtime loop."""
        while True:  # noqa: ASYNC110
            await asyncio.sleep(1)
            logger.debug("Async runtime tick")

    def run(self) -> None:
        """Run async runtime."""
        asyncio.run(self._test_async_runtime())

# Register workers
app.add_worker(
    "worker_1",
    "task_q_1",
    activities=[test_boost_activity_1, test_boost_activity_3],
)

app.add_worker("worker_2", "task_q_2", activities=[test_boost_activity_2])

# Worker with custom configuration
boost_worker = app.add_worker("worker_3", "task_q_3", workflows=[MyWorkflow])
boost_worker.configure_temporal_client(use_pydantic_data_converter=True)
boost_worker.configure_temporal_runtime(prometheus_bind_address="0.0.0.0:8801")

# Register ASGI worker
app.add_asgi_worker(
    "asgi_worker",
    "examples.example_asgi_app:fastapi_app",
    "0.0.0.0",
    8001,
    asgi_worker_type=ASGIWorkerType.hypercorn,
)

# Register custom exec method
app.add_exec_method_sync("migrate_db", fake_db_migration)

if __name__ == "__main__":
    app.run()
