"""
E-commerce order processing example for Temporal-boost.

This example demonstrates:
- Complex workflow with multiple activities
- Error handling
- Sequential activity execution
- Real-world use case

Run with: python3 example_ecommerce.py run all
"""

import logging
from datetime import timedelta

from pydantic import BaseModel
from temporalio import activity, workflow

from temporal_boost import BoostApp


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BoostApp(name="ecommerce-example", use_pydantic=True)


# Pydantic models
class Order(BaseModel):
    order_id: str
    customer_id: str
    items: list[dict]
    total: float


class PaymentResult(BaseModel):
    transaction_id: str
    status: str
    amount: float


# Activities
@activity.defn(name="validate_inventory")
async def validate_inventory(order: Order) -> dict:
    """Validate that all items are in stock."""
    logger.info(f"Validating inventory for order {order.order_id}")
    # Simulate inventory check
    return {"valid": True, "items_available": True, "order_id": order.order_id}


@activity.defn(name="process_payment")
async def process_payment(order: Order) -> PaymentResult:
    """Process payment for the order."""
    logger.info(f"Processing payment for order {order.order_id}: ${order.total}")
    # Simulate payment processing
    return PaymentResult(
        transaction_id=f"tx_{order.order_id}",
        status="completed",
        amount=order.total,
    )


@activity.defn(name="fulfill_order")
async def fulfill_order(order: Order) -> dict:
    """Fulfill the order (packaging, shipping, etc.)."""
    logger.info(f"Fulfilling order {order.order_id}")
    # Simulate order fulfillment
    return {
        "fulfilled": True,
        "shipping_id": f"ship_{order.order_id}",
        "tracking_number": f"TRACK{order.order_id}",
    }


@activity.defn(name="send_notification")
async def send_notification(order_id: str, status: str, message: str = "") -> dict:
    """Send notification to customer."""
    logger.info(f"Sending {status} notification for order {order_id}")
    # Simulate sending notification
    return {"sent": True, "order_id": order_id, "status": status}


# Workflow
@workflow.defn(sandboxed=False, name="OrderProcessingWorkflow")
class OrderProcessingWorkflow:
    """Complete order processing workflow."""

    @workflow.run
    async def run(self, order: Order) -> dict:
        """Process order through all steps."""
        logger.info(f"Starting order processing for {order.order_id}")

        try:
            # Step 1: Validate inventory
            validation = await workflow.execute_activity(
                validate_inventory,
                order,
                task_queue="inventory_queue",
                start_to_close_timeout=timedelta(minutes=5),
            )

            if not validation["valid"]:
                await workflow.execute_activity(
                    send_notification,
                    order.order_id,
                    "failed",
                    "Items out of stock",
                    task_queue="notification_queue",
                    start_to_close_timeout=timedelta(minutes=2),
                )
                return {"status": "failed", "reason": "inventory", "order_id": order.order_id}

            # Step 2: Process payment
            payment = await workflow.execute_activity(
                process_payment,
                order,
                task_queue="payment_queue",
                start_to_close_timeout=timedelta(minutes=10),
            )

            if payment.status != "completed":
                await workflow.execute_activity(
                    send_notification,
                    order.order_id,
                    "failed",
                    "Payment failed",
                    task_queue="notification_queue",
                    start_to_close_timeout=timedelta(minutes=2),
                )
                return {"status": "failed", "reason": "payment", "order_id": order.order_id}

            # Step 3: Fulfill order
            fulfillment = await workflow.execute_activity(
                fulfill_order,
                order,
                task_queue="fulfillment_queue",
                start_to_close_timeout=timedelta(minutes=30),
            )

            # Step 4: Send confirmation
            await workflow.execute_activity(
                send_notification,
                order.order_id,
                "completed",
                f"Order shipped! Tracking: {fulfillment['tracking_number']}",
                task_queue="notification_queue",
                start_to_close_timeout=timedelta(minutes=2),
            )

            return {
                "status": "completed",
                "order_id": order.order_id,
                "payment": payment.dict(),
                "fulfillment": fulfillment,
            }

        except Exception as e:
            logger.exception(f"Order processing failed: {e}")
            await workflow.execute_activity(
                send_notification,
                order.order_id,
                "failed",
                f"Order processing error: {e!s}",
                task_queue="notification_queue",
                start_to_close_timeout=timedelta(minutes=2),
            )
            raise


# Register workers
app.add_worker("inventory_worker", "inventory_queue", activities=[validate_inventory])
app.add_worker("payment_worker", "payment_queue", activities=[process_payment])
app.add_worker("fulfillment_worker", "fulfillment_queue", activities=[fulfill_order])
app.add_worker("notification_worker", "notification_queue", activities=[send_notification])
app.add_worker("order_workflow_worker", "workflow_queue", workflows=[OrderProcessingWorkflow])

if __name__ == "__main__":
    app.run()
