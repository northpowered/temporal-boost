"""
FastAPI integration example for Temporal-boost.

This example demonstrates:
- Running FastAPI alongside Temporal workers
- Starting workflows from HTTP endpoints
- Querying workflow status

Run with: python3 example_fastapi.py run all
Access API at: http://localhost:8000/docs
"""

import logging
from datetime import timedelta

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from temporalio import activity, workflow
from temporalio.client import Client

from temporal_boost import ASGIWorkerType, BoostApp


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BoostApp(name="fastapi-example")


# Pydantic models for API
class OrderRequest(BaseModel):
    order_id: str
    customer_id: str
    items: list[dict]
    total: float


class WorkflowResponse(BaseModel):
    workflow_id: str
    status: str


# Temporal activities
@activity.defn(name="process_order")
async def process_order(order_data: dict) -> dict:
    """Process an order."""
    logger.info(f"Processing order {order_data['order_id']}")
    return {"status": "processed", "order_id": order_data["order_id"]}


# Temporal workflow
@workflow.defn(sandboxed=False, name="OrderWorkflow")
class OrderWorkflow:
    """Simple order processing workflow."""

    def __init__(self) -> None:
        self.status = "pending"

    @workflow.run
    async def run(self, order_data: dict) -> dict:
        """Process order."""
        self.status = "processing"

        result = await workflow.execute_activity(
            process_order,
            order_data,
            task_queue="order_queue",
            start_to_close_timeout=timedelta(minutes=5),
        )

        self.status = "completed"
        return result

    @workflow.query(name="status")
    def get_status(self) -> dict:
        """Get workflow status."""
        return {"status": self.status}


# FastAPI application
fastapi_app = FastAPI(title="Temporal Order API", version="1.0.0")


@fastapi_app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@fastapi_app.post("/orders", response_model=WorkflowResponse)
async def create_order(order: OrderRequest):
    """Create a new order via Temporal workflow."""
    try:
        client = await Client.connect("localhost:7233")

        workflow_id = await client.start_workflow(
            "OrderWorkflow",
            order.dict(),
            id=f"order-{order.order_id}",
            task_queue="order_queue",
        )

        logger.info(f"Started workflow {workflow_id} for order {order.order_id}")

        return WorkflowResponse(
            workflow_id=workflow_id,
            status="started",
        )
    except Exception as e:
        logger.exception(f"Failed to start workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.get("/orders/{workflow_id}/status")
async def get_order_status(workflow_id: str):
    """Get order workflow status."""
    try:
        client = await Client.connect("localhost:7233")

        handle = client.get_workflow_handle(workflow_id)
        status = await handle.query("status")

        return {"workflow_id": workflow_id, "status": status}
    except Exception as e:
        logger.exception(f"Failed to query workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.get("/orders/{workflow_id}/result")
async def get_order_result(workflow_id: str):
    """Get order workflow result."""
    try:
        client = await Client.connect("localhost:7233")

        handle = client.get_workflow_handle(workflow_id)
        result = await handle.result()

        return {"workflow_id": workflow_id, "result": result}
    except Exception as e:
        logger.exception(f"Failed to get workflow result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Register Temporal worker
app.add_worker("order_worker", "order_queue", activities=[process_order], workflows=[OrderWorkflow])

# Register ASGI worker (FastAPI)
app.add_asgi_worker(
    "api_worker",
    fastapi_app,
    "0.0.0.0",
    8000,
    asgi_worker_type=ASGIWorkerType.auto,
)

if __name__ == "__main__":
    app.run()
