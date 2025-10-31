"""
Parallel activities example for Temporal-boost.

This example demonstrates:
- Executing multiple activities in parallel
- Using asyncio.gather for concurrent execution
- Aggregating results from parallel activities

Run with: python3 example_parallel.py run data_worker
"""

import asyncio
import logging
from datetime import timedelta

from temporalio import activity, workflow

from temporal_boost import BoostApp


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BoostApp(name="parallel-example")


@activity.defn(name="fetch_user_data")
async def fetch_user_data(user_id: str) -> dict:
    """Fetch user data from external service."""
    logger.info(f"Fetching user data for {user_id}")
    # Simulate API call
    await asyncio.sleep(1)
    return {"user_id": user_id, "name": f"User {user_id}", "email": f"{user_id}@example.com"}


@activity.defn(name="fetch_order_data")
async def fetch_order_data(order_id: str) -> dict:
    """Fetch order data from database."""
    logger.info(f"Fetching order data for {order_id}")
    # Simulate database query
    await asyncio.sleep(1)
    return {"order_id": order_id, "items": ["item1", "item2"], "total": 99.99}


@activity.defn(name="fetch_payment_data")
async def fetch_payment_data(payment_id: str) -> dict:
    """Fetch payment data from payment service."""
    logger.info(f"Fetching payment data for {payment_id}")
    # Simulate payment API call
    await asyncio.sleep(1)
    return {"payment_id": payment_id, "status": "completed", "amount": 99.99}


@workflow.defn(sandboxed=False, name="DataAggregationWorkflow")
class DataAggregationWorkflow:
    """Workflow that fetches data from multiple sources in parallel."""

    @workflow.run
    async def run(self, user_id: str, order_id: str, payment_id: str) -> dict:
        """Fetch and aggregate data from multiple sources."""
        logger.info(f"Starting data aggregation for user {user_id}")

        # Execute activities in parallel using asyncio.gather
        user_data, order_data, payment_data = await asyncio.gather(
            workflow.execute_activity(
                fetch_user_data,
                user_id,
                task_queue="data_queue",
                start_to_close_timeout=timedelta(minutes=5),
            ),
            workflow.execute_activity(
                fetch_order_data,
                order_id,
                task_queue="data_queue",
                start_to_close_timeout=timedelta(minutes=5),
            ),
            workflow.execute_activity(
                fetch_payment_data,
                payment_id,
                task_queue="data_queue",
                start_to_close_timeout=timedelta(minutes=5),
            ),
        )

        # Aggregate results
        result = {
            "user": user_data,
            "order": order_data,
            "payment": payment_data,
            "aggregated_at": workflow.now().isoformat(),
        }

        logger.info("Data aggregation completed")
        return result


app.add_worker(
    "data_worker",
    "data_queue",
    activities=[fetch_user_data, fetch_order_data, fetch_payment_data],
    workflows=[DataAggregationWorkflow],
)

if __name__ == "__main__":
    app.run()
