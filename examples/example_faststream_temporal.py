"""
FastStream integration example with Temporal workflows.

This example demonstrates:
- FastStream message consumers that trigger Temporal workflows
- Multiple message subscribers
- Error handling in message processing
- Integration between event-driven architecture and Temporal

Run with: python3 example_faststream_temporal.py run all
Requires Redis: docker run -p 6379:6379 redis:latest
"""

import logging
from datetime import timedelta

from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel
from temporalio import activity, workflow
from temporalio.client import Client

from temporal_boost import BoostApp


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Temporal-boost app
app = BoostApp(name="faststream-temporal-example")


# Pydantic models for messages
class OrderMessage(BaseModel):
    """Order message from queue."""
    order_id: str
    customer_id: str
    items: list[dict]
    total: float


class TaskMessage(BaseModel):
    """Task message from queue."""
    task_id: str
    description: str
    priority: int


# Temporal activities
@activity.defn(name="process_order")
async def process_order(order_data: dict) -> dict:
    """Process an order."""
    logger.info(f"Processing order {order_data['order_id']}")
    return {"status": "processed", "order_id": order_data["order_id"]}


@activity.defn(name="process_task")
async def process_task(task_data: dict) -> dict:
    """Process a task."""
    logger.info(f"Processing task {task_data['task_id']}")
    return {"status": "completed", "task_id": task_data["task_id"]}


# Temporal workflow
@workflow.defn(sandboxed=False, name="OrderWorkflow")
class OrderWorkflow:
    """Order processing workflow."""

    @workflow.run
    async def run(self, order_data: dict) -> dict:
        """Process order."""
        return await workflow.execute_activity(
            process_order,
            order_data,
            task_queue="order_queue",
            start_to_close_timeout=timedelta(minutes=5),
        )


# FastStream broker and app
broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)


@broker.subscriber("orders")
async def handle_order(message: OrderMessage) -> None:
    """Handle order messages from queue."""
    logger.info(f"Received order message: {message.order_id}")

    try:
        # Connect to Temporal and start workflow
        client = await Client.connect("localhost:7233")

        workflow_id = await client.start_workflow(
            "OrderWorkflow",
            message.dict(),
            id=f"order-{message.order_id}",
            task_queue="order_queue",
        )

        logger.info(f"Started Temporal workflow {workflow_id} for order {message.order_id}")

    except Exception as e:
        logger.exception(f"Failed to start workflow for order {message.order_id}: {e}")
        raise


@broker.subscriber("tasks")
async def handle_task(message: TaskMessage) -> None:
    """Handle task messages from queue."""
    logger.info(f"Received task message: {message.task_id} - {message.description}")

    try:
        # Connect to Temporal and execute activity directly
        await Client.connect("localhost:7233")

        # For high-priority tasks, execute activity directly
        if message.priority > 5:
            logger.info(f"Executing high-priority task {message.task_id} directly")
            # In a real scenario, you might want to use a workflow for complex tasks
            # For now, we'll just log it
        else:
            logger.info(f"Task {message.task_id} queued for processing")

    except Exception as e:
        logger.exception(f"Failed to process task {message.task_id}: {e}")
        raise


# Register Temporal worker
app.add_worker("order_worker", "order_queue", activities=[process_order], workflows=[OrderWorkflow])

# Register FastStream worker
app.add_faststream_worker("message_processor", faststream_app)

if __name__ == "__main__":
    app.run()
