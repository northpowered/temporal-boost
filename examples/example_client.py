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

import argparse
import asyncio
import contextlib
from typing import Any

from pydantic import BaseModel
from temporalio.client import Client


class Order(BaseModel):
    order_id: str
    customer_id: str
    items: list[dict[str, Any]]
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


async def start_order_workflow(order_data: dict[str, Any]) -> None:
    """Start an order processing workflow."""
    client = await Client.connect("localhost:7233")

    order = Order(**order_data)

    handle = await client.start_workflow(
        "OrderProcessingWorkflow",
        order,
        id=f"order-{order.order_id}",
        task_queue="workflow_queue",
    )

    # Wait for result
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
    """Parse commands and dispatch to the Temporal client."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start_workflow")
    start.add_argument("workflow_type", choices=["greeting", "order"])
    start.add_argument("identifier", nargs="?")
    start.add_argument("customer_id", nargs="?", default="customer-456")
    signal = commands.add_parser("send_signal")
    signal.add_argument("workflow_id")
    signal.add_argument("approved", choices=["true", "false"])
    signal.add_argument("comments", nargs="?", default="")
    for name in ("query_workflow", "get_result"):
        commands.add_parser(name).add_argument("workflow_id")
    args = parser.parse_args()
    if args.command == "start_workflow":
        if args.workflow_type == "greeting":
            await start_greeting_workflow(args.identifier or "World")
        else:
            await start_order_workflow({
                "order_id": args.identifier or "order-123",
                "customer_id": args.customer_id,
                "items": [{"item_id": "item1", "quantity": 1, "price": 99.99}],
                "total": 99.99,
            })
    elif args.command == "send_signal":
        await send_approval_signal(args.workflow_id, args.approved == "true", args.comments)
    elif args.command == "query_workflow":
        await query_workflow_status(args.workflow_id)
    else:
        await get_workflow_result(args.workflow_id)


if __name__ == "__main__":
    asyncio.run(main())
