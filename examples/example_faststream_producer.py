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

import argparse
import asyncio
from typing import Any

from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel


# Message models
class OrderMessage(BaseModel):
    order_id: str
    customer_id: str
    items: list[dict[str, Any]]
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
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    order = commands.add_parser("send_order")
    order.add_argument("order_id")
    order.add_argument("customer_id")
    task = commands.add_parser("send_task")
    task.add_argument("task_id")
    task.add_argument("description")
    task.add_argument("priority", type=int)
    args = parser.parse_args()
    async with broker:
        if args.command == "send_order":
            await send_order(args.order_id, args.customer_id)
        else:
            await send_task(args.task_id, args.description, args.priority)


if __name__ == "__main__":
    asyncio.run(main())
