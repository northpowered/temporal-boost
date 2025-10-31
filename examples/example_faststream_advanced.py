"""
Advanced FastStream example with multiple brokers and error handling.

This example demonstrates:
- Multiple message queues
- Error handling and retries
- Message filtering and routing
- Producer/consumer patterns

Run with: python3 example_faststream_advanced.py run message_processor
Requires Redis: docker run -p 6379:6379 redis:latest
"""

import logging
from datetime import timedelta

from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel, Field
from temporalio import activity, workflow
from temporalio.client import Client

from temporal_boost import BoostApp


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BoostApp(name="faststream-advanced-example")


# Message models
class EmailMessage(BaseModel):
    """Email notification message."""
    to: str
    subject: str
    body: str
    priority: str = Field(default="normal")


class NotificationMessage(BaseModel):
    """Notification message."""
    notification_id: str
    user_id: str
    type: str
    content: dict


# Temporal activities
@activity.defn(name="send_email")
async def send_email(email_data: dict) -> dict:
    """Send an email."""
    logger.info(f"Sending email to {email_data['to']}: {email_data['subject']}")
    # Simulate email sending
    return {"status": "sent", "to": email_data["to"]}


@activity.defn(name="send_notification")
async def send_notification(notification_data: dict) -> dict:
    """Send a notification."""
    logger.info(f"Sending notification {notification_data['notification_id']}")
    return {"status": "sent", "notification_id": notification_data["notification_id"]}


# Temporal workflow
@workflow.defn(sandboxed=False, name="NotificationWorkflow")
class NotificationWorkflow:
    """Notification processing workflow."""

    @workflow.run
    async def run(self, notification_data: dict) -> dict:
        """Process notification."""
        # Send notification
        result = await workflow.execute_activity(
            send_notification,
            notification_data,
            task_queue="notification_queue",
            start_to_close_timeout=timedelta(minutes=2),
        )

        # If it's an email notification, also send email
        if notification_data.get("type") == "email":
            await workflow.execute_activity(
                send_email,
                notification_data.get("content", {}),
                task_queue="notification_queue",
                start_to_close_timeout=timedelta(minutes=2),
            )

        return result


# FastStream setup
broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)


@broker.subscriber("emails", priority=True)
async def handle_email(message: EmailMessage) -> None:
    """Handle email messages with priority."""
    logger.info(f"Processing email: {message.subject} to {message.to}")

    try:
        client = await Client.connect("localhost:7233")

        # For high-priority emails, execute activity directly
        if message.priority == "high":
            logger.info("High-priority email, processing immediately")
            # You could execute activity directly here
            # For now, we'll use workflow for consistency

        # Start workflow for email processing
        workflow_id = await client.start_workflow(
            "NotificationWorkflow",
            {
                "notification_id": f"email-{message.to}",
                "user_id": message.to,
                "type": "email",
                "content": message.dict(),
            },
            id=f"email-{message.to}-{hash(message.subject)}",
            task_queue="notification_queue",
        )

        logger.info(f"Started workflow {workflow_id} for email")

    except Exception as e:
        logger.exception(f"Failed to process email: {e}")
        # In production, you might want to publish to a dead-letter queue
        raise


@broker.subscriber("notifications")
async def handle_notification(message: NotificationMessage) -> None:
    """Handle notification messages."""
    logger.info(f"Processing notification: {message.notification_id}")

    try:
        client = await Client.connect("localhost:7233")

        workflow_id = await client.start_workflow(
            "NotificationWorkflow",
            message.dict(),
            id=f"notif-{message.notification_id}",
            task_queue="notification_queue",
        )

        logger.info(f"Started workflow {workflow_id} for notification")

    except Exception as e:
        logger.exception(f"Failed to process notification: {e}")
        raise


# Register Temporal worker
app.add_worker(
    "notification_worker",
    "notification_queue",
    activities=[send_email, send_notification],
    workflows=[NotificationWorkflow],
)

# Register FastStream worker
app.add_faststream_worker("message_processor", faststream_app)

if __name__ == "__main__":
    app.run()
