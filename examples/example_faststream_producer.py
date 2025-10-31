"""
FastStream producer example for testing message queues.

This example demonstrates how to:
- Publish messages to FastStream queues
- Test FastStream consumers
- Send different message types

Usage:
  python3 example_faststream_producer.py send_order <order_id> <customer_id>
  python3 example_faststream_producer.py send_task <task_id> <description> <priority>
"""

import asyncio
import sys

from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel


# Message models
class OrderMessage(BaseModel):
    order_id: str
    customer_id: str
    items: list[dict]
    total: float


class TaskMessage(BaseModel):
    task_id: str
    description: str
    priority: int


# FastStream broker
broker = RedisBroker("redis://localhost:6379")
app = FastStream(broker)


async def send_order(order_id: str, customer_id: str) -> None:
    """Send an order message."""
    message = OrderMessage(
        order_id=order_id,
        customer_id=customer_id,
        items=[{"item_id": "item1", "quantity": 1, "price": 99.99}],
        total=99.99,
    )

    await broker.publish(message.dict(), "orders")


async def send_task(task_id: str, description: str, priority: int) -> None:
    """Send a task message."""
    message = TaskMessage(
        task_id=task_id,
        description=description,
        priority=priority,
    )

    await broker.publish(message.dict(), "tasks")


async def main() -> None:
    """Main CLI handler."""
    if len(sys.argv) < 2:
        sys.exit(1)

    command = sys.argv[1]

    if command == "send_order":
        if len(sys.argv) < 4:
            sys.exit(1)

        order_id = sys.argv[2]
        customer_id = sys.argv[3]
        await send_order(order_id, customer_id)

    elif command == "send_task":
        if len(sys.argv) < 5:
            sys.exit(1)

        task_id = sys.argv[2]
        description = sys.argv[3]
        priority = int(sys.argv[4])
        await send_task(task_id, description, priority)

    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
