# Examples

This page provides comprehensive examples covering common Temporal-boost patterns and use cases.

## Table of Contents

- [Basic Examples](#basic-examples)
- [Advanced Patterns](#advanced-patterns)
- [Integration Examples](#integration-examples)
- [Real-World Scenarios](#real-world-scenarios)

## Basic Examples

### Example 1: Simple Activity and Workflow

The most basic Temporal-boost application:

```python
import logging
from datetime import timedelta
from temporalio import activity, workflow
from temporal_boost import BoostApp

logging.basicConfig(level=logging.INFO)

app = BoostApp(name="simple-example")

@activity.defn(name="say_hello")
async def say_hello(name: str) -> str:
    return f"Hello, {name}!"

@workflow.defn(sandboxed=False, name="GreetingWorkflow")
class GreetingWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            say_hello,
            name,
            task_queue="greeting_queue",
            start_to_close_timeout=timedelta(minutes=1),
        )

app.add_worker(
    "greeting_worker",
    "greeting_queue",
    activities=[say_hello],
    workflows=[GreetingWorkflow],
)

if __name__ == "__main__":
    app.run()
```

### Example 2: Pydantic Models

Using Pydantic for type-safe data structures:

```python
from pydantic import BaseModel
from temporalio import activity, workflow
from temporal_boost import BoostApp

app = BoostApp(name="pydantic-example", use_pydantic=True)

class User(BaseModel):
    id: int
    name: str
    email: str

class UserResponse(BaseModel):
    user_id: int
    created_at: str
    status: str

@activity.defn(name="create_user")
async def create_user(user: User) -> UserResponse:
    # Simulate user creation
    return UserResponse(
        user_id=user.id,
        created_at="2024-01-01T00:00:00Z",
        status="created",
    )

@workflow.defn(sandboxed=False, name="UserCreationWorkflow")
class UserCreationWorkflow:
    @workflow.run
    async def run(self, user: User) -> UserResponse:
        return await workflow.execute_activity(
            create_user,
            user,
            task_queue="user_queue",
            start_to_close_timeout=timedelta(minutes=5),
        )

app.add_worker(
    "user_worker",
    "user_queue",
    activities=[create_user],
    workflows=[UserCreationWorkflow],
)

if __name__ == "__main__":
    app.run()
```

### Example 3: Multiple Activities in Sequence

```python
from datetime import timedelta
from temporalio import activity, workflow
from temporal_boost import BoostApp

app = BoostApp(name="multi-activity-example")

@activity.defn(name="validate_order")
async def validate_order(order_id: str) -> dict:
    return {"valid": True, "order_id": order_id}

@activity.defn(name="charge_payment")
async def charge_payment(order_id: str, amount: float) -> dict:
    return {"charged": True, "amount": amount}

@activity.defn(name="send_confirmation")
async def send_confirmation(order_id: str) -> dict:
    return {"sent": True, "order_id": order_id}

@workflow.defn(sandboxed=False, name="OrderWorkflow")
class OrderWorkflow:
    @workflow.run
    async def run(self, order_id: str, amount: float) -> dict:
        # Step 1: Validate
        validation = await workflow.execute_activity(
            validate_order,
            order_id,
            task_queue="order_queue",
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        if not validation["valid"]:
            return {"status": "failed", "reason": "validation"}
        
        # Step 2: Charge
        payment = await workflow.execute_activity(
            charge_payment,
            order_id,
            amount,
            task_queue="payment_queue",
            start_to_close_timeout=timedelta(minutes=10),
        )
        
        # Step 3: Confirm
        confirmation = await workflow.execute_activity(
            send_confirmation,
            order_id,
            task_queue="notification_queue",
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        return {
            "status": "completed",
            "order_id": order_id,
            "payment": payment,
            "confirmation": confirmation,
        }

app.add_worker("order_worker", "order_queue", activities=[validate_order])
app.add_worker("payment_worker", "payment_queue", activities=[charge_payment])
app.add_worker("notification_worker", "notification_queue", activities=[send_confirmation])
app.add_worker("workflow_worker", "workflow_queue", workflows=[OrderWorkflow])

if __name__ == "__main__":
    app.run()
```

## Advanced Patterns

### Example 4: Workflow with Signals

```python
from temporalio import workflow
from temporal_boost import BoostApp

app = BoostApp(name="signal-example")

@workflow.defn(sandboxed=False, name="ApprovalWorkflow")
class ApprovalWorkflow:
    def __init__(self):
        self.approved = False
        self.rejected = False
        self.comments = ""

    @workflow.run
    async def run(self, request_id: str) -> dict:
        await workflow.wait_condition(lambda: self.approved or self.rejected)
        
        return {
            "request_id": request_id,
            "status": "approved" if self.approved else "rejected",
            "comments": self.comments,
        }

    @workflow.signal(name="approve")
    def approve(self, comments: str = "") -> None:
        self.approved = True
        self.comments = comments

    @workflow.signal(name="reject")
    def reject(self, comments: str) -> None:
        self.rejected = True
        self.comments = comments

app.add_worker("approval_worker", "approval_queue", workflows=[ApprovalWorkflow])

if __name__ == "__main__":
    app.run()
```

### Example 5: CRON Worker

```python
from datetime import timedelta
from temporalio import activity, workflow
from temporal_boost import BoostApp

app = BoostApp(name="cron-example")

@activity.defn(name="generate_report")
async def generate_report() -> dict:
    # Generate daily report
    return {"report_id": "report_123", "generated_at": "2024-01-01"}

@workflow.defn(sandboxed=False, name="DailyReportWorkflow")
class DailyReportWorkflow:
    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            generate_report,
            task_queue="report_queue",
            start_to_close_timeout=timedelta(minutes=30),
        )

app.add_worker(
    "report_worker",
    "report_queue",
    activities=[generate_report],
    workflows=[DailyReportWorkflow],
    cron_schedule="0 0 * * *",  # Daily at midnight
    cron_runner=DailyReportWorkflow.run,
)

if __name__ == "__main__":
    app.run()
```

### Example 6: Parallel Activities

```python
import asyncio
from datetime import timedelta
from temporalio import activity, workflow
from temporal_boost import BoostApp

app = BoostApp(name="parallel-example")

@activity.defn(name="fetch_user_data")
async def fetch_user_data(user_id: str) -> dict:
    return {"user_id": user_id, "data": "user_data"}

@activity.defn(name="fetch_order_data")
async def fetch_order_data(order_id: str) -> dict:
    return {"order_id": order_id, "data": "order_data"}

@activity.defn(name="fetch_payment_data")
async def fetch_payment_data(payment_id: str) -> dict:
    return {"payment_id": payment_id, "data": "payment_data"}

@workflow.defn(sandboxed=False, name="DataAggregationWorkflow")
class DataAggregationWorkflow:
    @workflow.run
    async def run(self, user_id: str, order_id: str, payment_id: str) -> dict:
        # Execute activities in parallel
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
        
        return {
            "user": user_data,
            "order": order_data,
            "payment": payment_data,
        }

app.add_worker(
    "data_worker",
    "data_queue",
    activities=[fetch_user_data, fetch_order_data, fetch_payment_data],
    workflows=[DataAggregationWorkflow],
)

if __name__ == "__main__":
    app.run()
```

### Example 7: Activity Retry Policy

```python
from datetime import timedelta
from temporalio import activity
from temporalio.common import RetryPolicy
from temporal_boost import BoostApp

app = BoostApp(name="retry-example")

@activity.defn(
    name="unreliable_api_call",
    start_to_close_timeout=timedelta(seconds=30),
    retry_policy=RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=60),
        maximum_attempts=5,
    ),
)
async def unreliable_api_call(url: str) -> dict:
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

app.add_worker("api_worker", "api_queue", activities=[unreliable_api_call])

if __name__ == "__main__":
    app.run()
```

## Integration Examples

### Example 8: FastAPI Integration

```python
from fastapi import FastAPI
from temporal_boost import BoostApp, ASGIWorkerType
from temporalio.client import Client

app = BoostApp(name="fastapi-example")

# Create FastAPI app
fastapi_app = FastAPI(title="Temporal API")

@fastapi_app.get("/health")
async def health():
    return {"status": "healthy"}

@fastapi_app.post("/workflows")
async def start_workflow(workflow_data: dict):
    client = await Client.connect("localhost:7233")
    workflow_id = await client.start_workflow(
        "MyWorkflow",
        workflow_data,
        id=f"workflow-{workflow_data['id']}",
        task_queue="workflow_queue",
    )
    return {"workflow_id": workflow_id}

# Add ASGI worker
app.add_asgi_worker(
    "api_worker",
    fastapi_app,
    "0.0.0.0",
    8000,
    asgi_worker_type=ASGIWorkerType.auto,
)

if __name__ == "__main__":
    app.run()
```

### Example 9: FastStream Integration

Basic FastStream integration:

```python
from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel
from temporal_boost import BoostApp

app = BoostApp(name="faststream-example")

class TaskMessage(BaseModel):
    task_id: str
    description: str
    priority: int

broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("tasks")
async def process_task(message: TaskMessage):
    """Process task from message queue."""
    logger.info(f"Processing task: {message.task_id}")

app.add_faststream_worker("message_processor", faststream_app)

if __name__ == "__main__":
    app.run()
```

### Example 10: FastStream with Temporal Workflows

Integrate FastStream consumers with Temporal workflows:

```python
from faststream import FastStream
from faststream.redis import RedisBroker
from temporalio.client import Client
from temporalio import workflow
from temporal_boost import BoostApp
from datetime import timedelta
from pydantic import BaseModel

app = BoostApp(name="faststream-temporal")

class OrderMessage(BaseModel):
    order_id: str
    customer_id: str
    items: list[dict]
    total: float

@workflow.defn(sandboxed=False, name="OrderWorkflow")
class OrderWorkflow:
    @workflow.run
    async def run(self, order_data: dict) -> dict:
        # Process order...
        return {"status": "completed", "order_id": order_data["order_id"]}

broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("orders")
async def handle_order(message: OrderMessage):
    """Handle order and start Temporal workflow."""
    client = await Client.connect("localhost:7233")
    
    workflow_id = await client.start_workflow(
        "OrderWorkflow",
        message.dict(),
        id=f"order-{message.order_id}",
        task_queue="order_queue",
    )
    
    logger.info(f"Started workflow {workflow_id}")

app.add_worker("order_worker", "order_queue", workflows=[OrderWorkflow])
app.add_faststream_worker("message_processor", faststream_app)

if __name__ == "__main__":
    app.run()
```

### Example 11: Multiple FastStream Subscribers

Handle multiple message queues:

```python
from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel
from temporal_boost import BoostApp

app = BoostApp(name="faststream-multi")

class EmailMessage(BaseModel):
    to: str
    subject: str
    body: str

class NotificationMessage(BaseModel):
    notification_id: str
    user_id: str
    content: dict

broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("emails")
async def handle_email(message: EmailMessage):
    """Handle email messages."""
    logger.info(f"Processing email to {message.to}")

@broker.subscriber("notifications")
async def handle_notification(message: NotificationMessage):
    """Handle notification messages."""
    logger.info(f"Processing notification {message.notification_id}")

app.add_faststream_worker("message_processor", faststream_app)

if __name__ == "__main__":
    app.run()
```

## Real-World Scenarios

### Example 12: E-commerce Order Processing

```python
from datetime import timedelta
from pydantic import BaseModel
from temporalio import activity, workflow
from temporal_boost import BoostApp

app = BoostApp(name="ecommerce-example", use_pydantic=True)

class Order(BaseModel):
    order_id: str
    customer_id: str
    items: list[dict]
    total: float

class PaymentResult(BaseModel):
    transaction_id: str
    status: str

@activity.defn(name="validate_inventory")
async def validate_inventory(order: Order) -> dict:
    # Check inventory
    return {"valid": True, "items_available": True}

@activity.defn(name="process_payment")
async def process_payment(order: Order) -> PaymentResult:
    # Process payment
    return PaymentResult(
        transaction_id="tx_123",
        status="completed",
    )

@activity.defn(name="fulfill_order")
async def fulfill_order(order: Order) -> dict:
    # Fulfill order
    return {"fulfilled": True, "shipping_id": "ship_123"}

@activity.defn(name="send_notification")
async def send_notification(order_id: str, status: str) -> dict:
    # Send email notification
    return {"sent": True}

@workflow.defn(sandboxed=False, name="OrderProcessingWorkflow")
class OrderProcessingWorkflow:
    @workflow.run
    async def run(self, order: Order) -> dict:
        # Validate inventory
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
                task_queue="notification_queue",
                start_to_close_timeout=timedelta(minutes=2),
            )
            return {"status": "failed", "reason": "inventory"}
        
        # Process payment
        payment = await workflow.execute_activity(
            process_payment,
            order,
            task_queue="payment_queue",
            start_to_close_timeout=timedelta(minutes=10),
        )
        
        if payment.status != "completed":
            return {"status": "failed", "reason": "payment"}
        
        # Fulfill order
        fulfillment = await workflow.execute_activity(
            fulfill_order,
            order,
            task_queue="fulfillment_queue",
            start_to_close_timeout=timedelta(minutes=30),
        )
        
        # Send confirmation
        await workflow.execute_activity(
            send_notification,
            order.order_id,
            "completed",
            task_queue="notification_queue",
            start_to_close_timeout=timedelta(minutes=2),
        )
        
        return {
            "status": "completed",
            "order_id": order.order_id,
            "payment": payment.dict(),
            "fulfillment": fulfillment,
        }

app.add_worker("inventory_worker", "inventory_queue", activities=[validate_inventory])
app.add_worker("payment_worker", "payment_queue", activities=[process_payment])
app.add_worker("fulfillment_worker", "fulfillment_queue", activities=[fulfill_order])
app.add_worker("notification_worker", "notification_queue", activities=[send_notification])
app.add_worker("order_workflow_worker", "workflow_queue", workflows=[OrderProcessingWorkflow])

if __name__ == "__main__":
    app.run()
```

### Example 11: Data Processing Pipeline

```python
from datetime import timedelta
from temporalio import activity, workflow
from temporal_boost import BoostApp

app = BoostApp(name="data-processing-example")

@activity.defn(name="extract_data")
async def extract_data(source: str) -> dict:
    # Extract data from source
    return {"data": [1, 2, 3], "source": source}

@activity.defn(name="transform_data")
async def transform_data(data: dict) -> dict:
    # Transform data
    return {"data": [x * 2 for x in data["data"]], "transformed": True}

@activity.defn(name="load_data")
async def load_data(data: dict, destination: str) -> dict:
    # Load data to destination
    return {"loaded": True, "destination": destination, "records": len(data["data"])}

@workflow.defn(sandboxed=False, name="ETLWorkflow")
class ETLWorkflow:
    @workflow.run
    async def run(self, source: str, destination: str) -> dict:
        # Extract
        extracted = await workflow.execute_activity(
            extract_data,
            source,
            task_queue="etl_queue",
            start_to_close_timeout=timedelta(minutes=10),
        )
        
        # Transform
        transformed = await workflow.execute_activity(
            transform_data,
            extracted,
            task_queue="etl_queue",
            start_to_close_timeout=timedelta(minutes=15),
        )
        
        # Load
        loaded = await workflow.execute_activity(
            load_data,
            transformed,
            destination,
            task_queue="etl_queue",
            start_to_close_timeout=timedelta(minutes=20),
        )
        
        return {
            "status": "completed",
            "source": source,
            "destination": destination,
            "records_processed": loaded["records"],
        }

app.add_worker(
    "etl_worker",
    "etl_queue",
    activities=[extract_data, transform_data, load_data],
    workflows=[ETLWorkflow],
)

if __name__ == "__main__":
    app.run()
```

These examples demonstrate common patterns and use cases. For more advanced patterns, see [Advanced Usage](advanced_usage.md).

