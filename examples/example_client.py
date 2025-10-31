"""
Client example for testing workflows.

This example demonstrates how to:
- Connect to Temporal server
- Start workflows
- Send signals to workflows
- Query workflow status
- Get workflow results

Usage:
  python3 example_client.py start_workflow <workflow_type> <args>
  python3 example_client.py send_signal <workflow_id> <signal_name> <args>
  python3 example_client.py query_workflow <workflow_id>
  python3 example_client.py get_result <workflow_id>
"""

import asyncio
import contextlib
import sys

from pydantic import BaseModel
from temporalio.client import Client


class Order(BaseModel):
    order_id: str
    customer_id: str
    items: list[dict]
    total: float


async def start_greeting_workflow(name: str) -> None:
    """Start a greeting workflow."""
    client = await Client.connect("localhost:7233")

    await client.execute_workflow(
        "GreetingWorkflow",
        name,
        id=f"greeting-{name}",
        task_queue="greeting_queue",
    )


async def start_order_workflow(order_data: dict) -> None:
    """Start an order processing workflow."""
    client = await Client.connect("localhost:7233")

    order = Order(**order_data)

    workflow_id = await client.start_workflow(
        "OrderProcessingWorkflow",
        order,
        id=f"order-{order.order_id}",
        task_queue="workflow_queue",
    )

    # Wait for result
    handle = client.get_workflow_handle(workflow_id)
    await handle.result()


async def send_approval_signal(workflow_id: str, approved: bool, comments: str = "") -> None:
    """Send approval or rejection signal to workflow."""
    client = await Client.connect("localhost:7233")

    handle = client.get_workflow_handle(workflow_id)

    if approved:
        await handle.signal("approve", comments)
    else:
        await handle.signal("reject", comments)

    # Get result
    await handle.result()


async def query_workflow_status(workflow_id: str) -> None:
    """Query workflow status."""
    client = await Client.connect("localhost:7233")

    handle = client.get_workflow_handle(workflow_id)

    with contextlib.suppress(Exception):
        await handle.query("status")


async def get_workflow_result(workflow_id: str) -> None:
    """Get workflow result."""
    client = await Client.connect("localhost:7233")

    handle = client.get_workflow_handle(workflow_id)

    with contextlib.suppress(Exception):
        await handle.result()


async def main() -> None:
    """Main CLI handler."""
    if len(sys.argv) < 2:
        sys.exit(1)

    command = sys.argv[1]

    if command == "start_workflow":
        workflow_type = sys.argv[2] if len(sys.argv) > 2 else None

        if workflow_type == "greeting":
            name = sys.argv[3] if len(sys.argv) > 3 else "World"
            await start_greeting_workflow(name)

        elif workflow_type == "order":
            order_id = sys.argv[3] if len(sys.argv) > 3 else "order-123"
            customer_id = sys.argv[4] if len(sys.argv) > 4 else "customer-456"

            order_data = {
                "order_id": order_id,
                "customer_id": customer_id,
                "items": [{"item_id": "item1", "quantity": 1, "price": 99.99}],
                "total": 99.99,
            }
            await start_order_workflow(order_data)

        else:
            sys.exit(1)

    elif command == "send_signal":
        if len(sys.argv) < 4:
            sys.exit(1)

        workflow_id = sys.argv[2]
        approved = sys.argv[3].lower() == "true"
        comments = sys.argv[4] if len(sys.argv) > 4 else ""

        await send_approval_signal(workflow_id, approved, comments)

    elif command == "query_workflow":
        if len(sys.argv) < 3:
            sys.exit(1)

        workflow_id = sys.argv[2]
        await query_workflow_status(workflow_id)

    elif command == "get_result":
        if len(sys.argv) < 3:
            sys.exit(1)

        workflow_id = sys.argv[2]
        await get_workflow_result(workflow_id)

    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
