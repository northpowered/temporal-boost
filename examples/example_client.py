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
import sys
from temporalio.client import Client
from pydantic import BaseModel


class Order(BaseModel):
    order_id: str
    customer_id: str
    items: list[dict]
    total: float


async def start_greeting_workflow(name: str):
    """Start a greeting workflow."""
    client = await Client.connect("localhost:7233")
    
    result = await client.execute_workflow(
        "GreetingWorkflow",
        name,
        id=f"greeting-{name}",
        task_queue="greeting_queue",
    )
    
    print(f"Workflow result: {result}")


async def start_order_workflow(order_data: dict):
    """Start an order processing workflow."""
    client = await Client.connect("localhost:7233")
    
    order = Order(**order_data)
    
    workflow_id = await client.start_workflow(
        "OrderProcessingWorkflow",
        order,
        id=f"order-{order.order_id}",
        task_queue="workflow_queue",
    )
    
    print(f"Started workflow: {workflow_id}")
    
    # Wait for result
    handle = client.get_workflow_handle(workflow_id)
    result = await handle.result()
    
    print(f"Workflow result: {result}")


async def send_approval_signal(workflow_id: str, approved: bool, comments: str = ""):
    """Send approval or rejection signal to workflow."""
    client = await Client.connect("localhost:7233")
    
    handle = client.get_workflow_handle(workflow_id)
    
    if approved:
        await handle.signal("approve", comments)
        print(f"Sent approval signal to {workflow_id}")
    else:
        await handle.signal("reject", comments)
        print(f"Sent rejection signal to {workflow_id}")
    
    # Get result
    result = await handle.result()
    print(f"Workflow result: {result}")


async def query_workflow_status(workflow_id: str):
    """Query workflow status."""
    client = await Client.connect("localhost:7233")
    
    handle = client.get_workflow_handle(workflow_id)
    
    try:
        status = await handle.query("status")
        print(f"Workflow {workflow_id} status: {status}")
    except Exception as e:
        print(f"Error querying workflow: {e}")


async def get_workflow_result(workflow_id: str):
    """Get workflow result."""
    client = await Client.connect("localhost:7233")
    
    handle = client.get_workflow_handle(workflow_id)
    
    try:
        result = await handle.result()
        print(f"Workflow {workflow_id} result: {result}")
    except Exception as e:
        print(f"Error getting result: {e}")


async def main():
    """Main CLI handler."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 example_client.py start_workflow greeting <name>")
        print("  python3 example_client.py start_workflow order <order_id> <customer_id>")
        print("  python3 example_client.py send_signal <workflow_id> <approved> [comments]")
        print("  python3 example_client.py query_workflow <workflow_id>")
        print("  python3 example_client.py get_result <workflow_id>")
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
            print(f"Unknown workflow type: {workflow_type}")
            sys.exit(1)
    
    elif command == "send_signal":
        if len(sys.argv) < 4:
            print("Usage: python3 example_client.py send_signal <workflow_id> <approved> [comments]")
            sys.exit(1)
        
        workflow_id = sys.argv[2]
        approved = sys.argv[3].lower() == "true"
        comments = sys.argv[4] if len(sys.argv) > 4 else ""
        
        await send_approval_signal(workflow_id, approved, comments)
    
    elif command == "query_workflow":
        if len(sys.argv) < 3:
            print("Usage: python3 example_client.py query_workflow <workflow_id>")
            sys.exit(1)
        
        workflow_id = sys.argv[2]
        await query_workflow_status(workflow_id)
    
    elif command == "get_result":
        if len(sys.argv) < 3:
            print("Usage: python3 example_client.py get_result <workflow_id>")
            sys.exit(1)
        
        workflow_id = sys.argv[2]
        await get_workflow_result(workflow_id)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

