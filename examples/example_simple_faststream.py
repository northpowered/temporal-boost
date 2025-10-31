"""
Simple FastStream example for Temporal-boost.

This example demonstrates:
- Basic FastStream integration
- Message queue processing
- Simple message consumer

Run with: python3 example_simple_faststream.py run message_processor
Requires Redis: docker run -p 6379:6379 redis:latest
"""

import logging

from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel

from temporal_boost import BoostApp


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Message model
class TaskMessage(BaseModel):
    """Task message model."""
    task_id: str
    description: str
    priority: int


# Initialize FastStream broker and app
broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)


@broker.subscriber("tasks")
async def process_task(message: TaskMessage) -> None:
    """Process task messages from queue."""
    logger.info(f"Processing task: {message.task_id} - {message.description}")

    if message.priority > 5:  # noqa: PLR2004
        logger.info(f"High priority task {message.task_id} processed immediately")
    else:
        logger.info(f"Normal priority task {message.task_id} queued for processing")


# Initialize Temporal-boost app
boost_app = BoostApp("simple-faststream-example")

# Register FastStream worker
boost_app.add_faststream_worker("message_processor", faststream_app)

if __name__ == "__main__":
    boost_app.run()
