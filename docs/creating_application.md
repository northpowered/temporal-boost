# Creating application

This guide covers everything you need to know about creating Temporal-boost applications, from basic setup to advanced patterns.

## Table of Contents

- [Application Structure](#application-structure)
- [BoostApp Initialization](#boostapp-initialization)
- [Defining Activities](#defining-activities)
- [Defining Workflows](#defining-workflows)
- [Adding Workers](#adding-workers)
- [CRON Workers](#cron-workers)
- [ASGI Workers](#asgi-workers)
- [FastStream Workers](#faststream-workers)
- [Best Practices](#best-practices)

## Application Structure

A typical Temporal-boost application follows this structure:

```
my_app/
├── main.py              # Application entry point
├── activities.py        # Activity definitions
├── workflows.py         # Workflow definitions
├── config.py            # Configuration (optional)
└── requirements.txt     # Dependencies
```

## BoostApp Initialization

The `BoostApp` class is the central component of your application. Initialize it at the start of your application:

```python
from temporal_boost import BoostApp

app = BoostApp(
    name="my-service",              # Application name (optional)
    temporal_endpoint=None,          # Override TEMPORAL_TARGET_HOST (optional)
    temporal_namespace=None,         # Override TEMPORAL_NAMESPACE (optional)
    debug_mode=False,                # Enable debug mode (optional)
    use_pydantic=None,               # Override Pydantic converter (optional)
    logger_config=None,              # Custom logging config (optional)
)
```

### Configuration Priority

Endpoint and namespace are selected independently in this order (highest to lowest priority):

1. **Explicit worker configuration** via `worker.configure_temporal_client(target_host=..., namespace=...)`
2. **BoostApp initialization parameters**
3. **Environment variables read at import**
4. **Built-in default values** (`localhost:7233` and `default`)

For example, with `TEMPORAL_TARGET_HOST=temporal.prod:7233` in the environment,
`BoostApp(temporal_endpoint="temporal.dev:7233")` selects `temporal.dev:7233`. A later explicit
worker configuration can override that address before client initialization. On an existing builder,
omitted fields and `None` leave previous settings unchanged; the last explicit value for each field wins.

Environment values are read when `temporal_boost` is first imported. The package does not load `.env`
automatically, and changing `os.environ` after import does not update configuration defaults.
Load environment files before the first package import, or prepare the environment before starting
the installed CLI. Boolean flags, numeric options, empty strings, and runtime defaults have distinct
rules; see the [configuration guide](configuration.md#configuration-priority) and
[environment loading](configuration.md#environment-loading).

## Defining Activities

Activities are functions that perform actual work. They should be deterministic-free and can perform I/O operations.

### Basic Activity

```python
from temporalio import activity

@activity.defn(name="process_payment")
async def process_payment(amount: float, currency: str) -> dict:
    """Process a payment transaction."""
    # Your business logic here
    return {"status": "success", "amount": amount, "currency": currency}
```

### Activity with Pydantic Models

Using Pydantic models provides type safety and validation:

```python
from pydantic import BaseModel
from temporalio import activity

class PaymentRequest(BaseModel):
    amount: float
    currency: str
    customer_id: str

class PaymentResponse(BaseModel):
    transaction_id: str
    status: str
    amount: float

@activity.defn(name="process_payment")
async def process_payment(request: PaymentRequest) -> PaymentResponse:
    """Process a payment with type-safe models."""
    # Process payment...
    return PaymentResponse(
        transaction_id="tx_123",
        status="completed",
        amount=request.amount,
    )
```

### Activity with Retry Options

Activities can have custom retry policies:

```python
from temporalio import activity
from temporalio.common import RetryPolicy

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
    """Activity with custom retry policy."""
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

### Activity Best Practices

- ✅ Keep activities idempotent when possible
- ✅ Use appropriate timeouts (`start_to_close_timeout`)
- ✅ Handle errors gracefully
- ✅ Use Pydantic models for complex data structures
- ✅ Log important operations
- ❌ Don't use random numbers or current time in activities
- ❌ Don't perform operations that can't be retried

## Defining Workflows

Workflows orchestrate activities and define business logic. They must be deterministic.

### Basic Workflow

```python
from datetime import timedelta
from temporalio import workflow

@workflow.defn(sandboxed=False, name="OrderProcessingWorkflow")
class OrderProcessingWorkflow:
    @workflow.run
    async def run(self, order_id: str) -> dict:
        """Process an order through multiple steps."""
        # Step 1: Validate order
        validation_result = await workflow.execute_activity(
            validate_order,
            order_id,
            task_queue="order_queue",
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        if not validation_result["valid"]:
            return {"status": "failed", "reason": "validation_failed"}
        
        # Step 2: Process payment
        payment_result = await workflow.execute_activity(
            process_payment,
            validation_result["amount"],
            task_queue="payment_queue",
            start_to_close_timeout=timedelta(minutes=10),
        )
        
        # Step 3: Fulfill order
        fulfillment_result = await workflow.execute_activity(
            fulfill_order,
            order_id,
            task_queue="fulfillment_queue",
            start_to_close_timeout=timedelta(minutes=30),
        )
        
        return {
            "status": "completed",
            "order_id": order_id,
            "payment": payment_result,
            "fulfillment": fulfillment_result,
        }
```

### Workflow with Signals

Signals allow external systems to send data to running workflows:

```python
from temporalio import workflow

@workflow.defn(sandboxed=False, name="ApprovalWorkflow")
class ApprovalWorkflow:
    def __init__(self):
        self.approved = False
        self.rejected = False

    @workflow.run
    async def run(self, request_id: str) -> dict:
        """Wait for approval signal."""
        await workflow.wait_condition(lambda: self.approved or self.rejected)
        
        if self.approved:
            return {"status": "approved", "request_id": request_id}
        return {"status": "rejected", "request_id": request_id}

    @workflow.signal(name="approve")
    def approve(self) -> None:
        """Signal handler for approval."""
        self.approved = True

    @workflow.signal(name="reject")
    def reject(self) -> None:
        """Signal handler for rejection."""
        self.rejected = True
```

### Workflow with Queries

Queries allow reading workflow state without affecting execution:

```python
from temporalio import workflow

@workflow.defn(sandboxed=False, name="OrderStatusWorkflow")
class OrderStatusWorkflow:
    def __init__(self):
        self.status = "pending"
        self.progress = 0

    @workflow.run
    async def run(self, order_id: str) -> dict:
        """Process order and update status."""
        self.status = "processing"
        await workflow.execute_activity(
            process_order,
            order_id,
            task_queue="order_queue",
            start_to_close_timeout=timedelta(minutes=30),
        )
        self.status = "completed"
        self.progress = 100
        return {"status": self.status, "order_id": order_id}

    @workflow.query(name="status")
    def get_status(self) -> dict:
        """Query workflow status."""
        return {"status": self.status, "progress": self.progress}
```

### Workflow Best Practices

- ✅ Keep workflows deterministic (no random, no time, no I/O)
- ✅ Use appropriate timeouts for activities
- ✅ Handle errors with try/except blocks
- ✅ Use signals for external input
- ✅ Use queries for state inspection
- ✅ Use `sandboxed=False` for most workflows (better performance)
- ❌ Don't use `datetime.now()` - use `workflow.now()`
- ❌ Don't perform I/O operations directly

## Adding Workers

Workers connect your activities and workflows to Temporal task queues.

### Basic Worker Registration

```python
app.add_worker(
    worker_name="payment_worker",
    task_queue="payment_queue",
    activities=[process_payment, refund_payment],
    workflows=[PaymentWorkflow],
)
```

### Worker Parameters

The `add_worker` method accepts:

```python
app.add_worker(
    worker_name: str,                    # Unique worker name
    task_queue: str,                     # Temporal task queue name
    activities: list[Callable] | None,   # List of activity functions
    workflows: list[type] | None,        # List of workflow classes
    interceptors: list[Interceptor] | None,  # Optional interceptors
    cron_schedule: str | None,           # CRON schedule (for CRON workers)
    cron_runner: Callable | None,        # CRON runner method
    cron_workflow_id: str | None,        # Stable workflow ID (optional override)
    **worker_kwargs: Any,                # Additional worker options
) -> TemporalBoostWorker
```

### Multiple Workers Example

```python
# Activity-only worker
app.add_worker(
    "payment_activities",
    "payment_queue",
    activities=[process_payment, refund_payment, validate_payment],
)

# Workflow-only worker
app.add_worker(
    "order_workflows",
    "order_queue",
    workflows=[OrderWorkflow, RefundWorkflow],
)

# Combined worker
app.add_worker(
    "combined_worker",
    "main_queue",
    activities=[process_order, send_notification],
    workflows=[OrderWorkflow],
)
```

### Worker Configuration

After adding a worker, you can configure it further:

```python
worker = app.add_worker(
    "custom_worker",
    "custom_queue",
    activities=[my_activity],
)

# Configure Temporal client
worker.configure_temporal_client(
    target_host="custom-host:7233",
    namespace="custom_namespace",
    use_pydantic_data_converter=True,
)

# Configure runtime with Prometheus metrics
worker.configure_temporal_runtime(
    prometheus_bind_address="0.0.0.0:9090",
)
```

## CRON Workers

CRON workers configure server-side recurring workflows. Calling `add_worker()` stores configuration
and registers CLI commands locally. Use `cron <name>` to create or reuse the server-side chain and
consume its task queue; `run <name>` and `run all` only consume queues.

### Creating a CRON Worker

```python
@workflow.defn(sandboxed=False, name="DailyReportWorkflow")
class DailyReportWorkflow:
    @workflow.run
    async def run(self) -> None:
        """Generate daily report."""
        await workflow.execute_activity(
            generate_report,
            task_queue="report_queue",
            start_to_close_timeout=timedelta(minutes=30),
        )

app.add_worker(
    "daily_report_cron",
    "report_queue",
    workflows=[DailyReportWorkflow],
    cron_schedule="0 0 * * *",  # Run at midnight every day
    cron_runner=DailyReportWorkflow.run,
    cron_workflow_id="reports/daily-v1",  # Same ID on every replica and restart
)
```

Provide both `cron_schedule` and `cron_runner`, or omit both for an ordinary consumer. A partial pair
or an empty/whitespace-only schedule raises `ValueError` immediately, before any connection is opened.
The same validation applies to direct `TemporalBoostWorker(...)` construction. The SDK/server validates
the CRON expression syntax at registration. To migrate a previously accepted partial configuration,
either supply the missing parameter or remove the CRON options. An explicit `cron_workflow_id` alone
does not enable CRON mode.

### CRON Workflow Identity

`cron_workflow_id` identifies one logical CRON job within a Temporal namespace. It is also supported
when constructing `TemporalBoostWorker` directly. If omitted, the ID is
`temporal-boost/cron/<escaped task_queue>/<escaped worker_name>`; each component is URL percent-encoded
(including `/` and `%`). For example, queue `report_queue` and worker `daily_report_cron` produce
`temporal-boost/cron/report_queue/daily_report_cron`. Explicit IDs must contain a non-whitespace character
and are otherwise preserved exactly.

Keep queue and worker name stable when using the default. Supply an explicit ID to preserve identity
across renames or queue moves. Independent jobs sharing the same queue and worker name need distinct
explicit IDs; replicas of one job must use the same ID and namespace.

Registration uses server-side `WorkflowIDConflictPolicy.USE_EXISTING` for a running workflow and
`WorkflowIDReusePolicy.REJECT_DUPLICATE` for a closed workflow. Concurrent processes and restarts reuse
the active chain atomically. A completed, failed, cancelled, or terminated ID raises the SDK's
`WorkflowAlreadyStartedError`; registration does not generate a replacement ID. Closed-ID protection
lasts only while Temporal retains the execution history. A running workflow with that ID is reused
even if it was created outside this application, so reserve IDs for their intended jobs.

Reusing an active workflow does not update its workflow type, task queue, or CRON expression. Treat
configuration changes as an explicit migration. Registration logs include namespace, workflow ID,
and the run ID returned by the server; "registered or already running" covers both creation and reuse.

This continues to use SDK `cron_schedule`, rather than Temporal Schedules. Local shutdown leaves the
server-side CRON chain in place. Before upgrading from random UUID IDs, follow the
[migration procedure](running_application.md#migrating-existing-uuid-cron-workflows).

### CRON Schedule Format

CRON schedules use standard format: `minute hour day month weekday`

Examples:

- `"0 * * * *"` - Every hour at minute 0
- `"0 0 * * *"` - Every day at midnight
- `"0 9 * * 1"` - Every Monday at 9 AM
- `"*/5 * * * *"` - Every 5 minutes
- `"0 0 1 * *"` - First day of every month

### Running CRON Workers

```bash
# Register/reuse the server-side chain and consume the queue
python3 main.py cron daily_report_cron

# Consume the queue for an already registered chain
python3 main.py run daily_report_cron

# Run all consumers; this does not create schedules
python3 main.py run all
```

Only workers with both CRON parameters receive a `cron <name>` command. Direct `worker.cron()` requires
that configuration too and raises `RuntimeError` before starting a loop or connecting when it is absent.
Registration runs once per CRON process start; Temporal continues the chain on the server. The process
keeps consuming until stopped, and local stop leaves the server-side chain in place.

## ASGI Workers

ASGI workers allow you to run FastAPI, Starlette, or any ASGI application alongside your Temporal workers.

### Basic ASGI Worker

```python
from fastapi import FastAPI
from temporal_boost import BoostApp, ASGIWorkerType

app = BoostApp("my-service")

# Create your FastAPI app
fastapi_app = FastAPI(title="My API")

@fastapi_app.get("/health")
async def health():
    return {"status": "healthy"}

# Add ASGI worker
app.add_asgi_worker(
    "api_worker",
    fastapi_app,
    host="0.0.0.0",
    port=8000,
    asgi_worker_type=ASGIWorkerType.auto,  # Priority: Uvicorn, Granian, Hypercorn
)
```

### Specifying ASGI Server

```python
# Use Uvicorn
app.add_asgi_worker(
    "api_worker",
    fastapi_app,
    "0.0.0.0",
    8000,
    asgi_worker_type=ASGIWorkerType.uvicorn,
)

# Use Hypercorn
app.add_asgi_worker(
    "api_worker",
    fastapi_app,
    "0.0.0.0",
    8000,
    asgi_worker_type=ASGIWorkerType.hypercorn,
)

# Use Granian
app.add_asgi_worker(
    "api_worker",
    fastapi_app,
    "0.0.0.0",
    8000,
    asgi_worker_type=ASGIWorkerType.granian,
)
```

### ASGI Worker from String Path

You can also load ASGI apps from a string path:

```python
app.add_asgi_worker(
    "api_worker",
    "myapp.api:app",  # Module path to ASGI app
    "0.0.0.0",
    8000,
)
```

### Managed ASGI Shutdown

Uvicorn, Hypercorn, and Granian workers support `BoostApp.stop()` under `run all`. Their serving
tasks and cleanup share one event loop per run. The coordinator requests stop from another thread
and waits up to `BoostApp(shutdown_timeout=...)`; it never runs server cleanup in a separate loop.
Main-thread runs handle SIGINT/SIGTERM and restore the previous handlers. Worker threads leave
process signal handling to the coordinator or CLI supervisor.

The lifecycle is verified with HTTP requests and ASGI lifespan counters against the lockfile versions:

| Backend | Serving API | Stop mechanism | Application |
| --- | --- | --- | --- |
| Uvicorn 0.35.0 | `Server.serve()` | Set `should_exit` after startup completes | Object or `module:attribute`; `factory=True` supported |
| Hypercorn 0.17.3 | `hypercorn.asyncio.serve()` | `shutdown_trigger` completes | Object or `module:attribute`; pass an already-created app |
| Granian 2.4.2 | `granian.server.embed.Server.serve()` | Public `stop()`, then join serving task | Object or `module:attribute`; `factory=True` supported |

Normal cleanup belongs to the serving API. The adapter does not call server shutdown again after
it finishes. Uvicorn also receives cleanup if an error interrupts its main loop. Explicit lifespan
startup/shutdown failure messages produce errors, including on Granian, which otherwise only records
some lifespan failures internally. Import and startup errors reach the caller.

Built-in adapters expose a thread-safe, repeatable `worker.request_stop()`. Async `worker.shutdown()`
is harmless before or after a run; on the owning loop it requests stop and waits for cleanup.
Use `request_stop()` from another loop or an ASGI callback. Cancelling a shutdown waiter does not
cancel cleanup. A stop before the first run creates no server resources; a completed adapter can
run again on a fresh loop. An in-progress startup hook is allowed to finish before graceful shutdown.
A hook that never finishes can exceed the coordinator's budget.

These adapters run one server in the worker's asyncio loop. Set `workers=1` and disable backend
reloaders (`reload=False`, or `use_reloader=False` for Hypercorn). Other worker counts and reloaders
are rejected. Explicit loop choices are limited to `asyncio`/`auto` for Uvicorn and Granian;
Hypercorn requires `worker_class="asyncio"` and `debug=False`. The adapter owns loop setup.
Configure process scaling through separate HTTP deployments as described in
[ASGI and external processes](running_application.md#asgi-and-external-processes).

Migration: Granian now uses its experimental embedded async server, so options must belong to that
server's constructor. Process-manager options such as `workers_lifetime` are unavailable. Hypercorn
kwargs must name existing configuration fields; misspellings now raise an error. Hypercorn does
not accept a `factory` option through this API: call the factory yourself and pass its result.
Uvicorn and Granian reject custom loop choices instead of silently changing global loop policy.

### ASGI Worker with Temporal Integration

Combine ASGI endpoints with Temporal workflows:

```python
from fastapi import FastAPI
from temporalio.client import Client

fastapi_app = FastAPI()

@fastapi_app.post("/orders")
async def create_order(order_data: dict):
    """Create an order via Temporal workflow."""
    client = await Client.connect("localhost:7233")
    workflow_id = await client.start_workflow(
        "OrderWorkflow",
        order_data,
        id=f"order-{order_data['id']}",
        task_queue="order_queue",
    )
    return {"workflow_id": workflow_id}
```

## FastStream Workers

FastStream workers integrate event-driven architectures with Temporal. FastStream is a framework for building async message consumers and producers, supporting multiple message brokers (Redis, RabbitMQ, Kafka, etc.).

### Basic FastStream Worker

```python
from faststream import FastStream
from faststream.redis import RedisBroker
from temporal_boost import BoostApp

# Initialize FastStream broker and app
broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("tasks")
async def process_task(message: dict):
    """Process task from message queue."""
    logger.info(f"Processing task: {message['task_id']}")

app = BoostApp("event-driven-service")
app.add_faststream_worker("message_processor", faststream_app)
```

### FastStream with Pydantic Models

Use Pydantic models for type-safe message handling:

```python
from pydantic import BaseModel
from faststream import FastStream
from faststream.redis import RedisBroker
from temporal_boost import BoostApp

class OrderMessage(BaseModel):
    order_id: str
    customer_id: str
    items: list[dict]
    total: float

broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("orders")
async def handle_order(message: OrderMessage):
    """Handle order messages."""
    logger.info(f"Received order: {message.order_id}")

app = BoostApp("order-service")
app.add_faststream_worker("order_processor", faststream_app)
```

### FastStream with Temporal Workflows

Combine FastStream message consumers with Temporal workflows:

```python
from faststream import FastStream
from faststream.redis import RedisBroker
from temporalio.client import Client
from temporalio import activity, workflow
from temporal_boost import BoostApp
from datetime import timedelta

app = BoostApp("faststream-temporal")

# Temporal workflow
@workflow.defn(sandboxed=False, name="OrderWorkflow")
class OrderWorkflow:
    @workflow.run
    async def run(self, order_data: dict) -> dict:
        # Process order...
        return {"status": "completed"}

# FastStream app
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

# Register both workers
app.add_worker("order_worker", "order_queue", workflows=[OrderWorkflow])
app.add_faststream_worker("message_processor", faststream_app)
```

### Multiple Message Queues

Handle multiple message queues:

```python
broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("orders")
async def handle_orders(message: OrderMessage):
    """Handle order messages."""
    # Process orders...

@broker.subscriber("notifications")
async def handle_notifications(message: NotificationMessage):
    """Handle notification messages."""
    # Process notifications...

app.add_faststream_worker("message_processor", faststream_app)
```

### FastStream with Different Brokers

FastStream supports multiple brokers. Examples:

**Redis:**
```python
from faststream.redis import RedisBroker
broker = RedisBroker("redis://localhost:6379")
```

**RabbitMQ:**
```python
from faststream.rabbit import RabbitBroker
broker = RabbitBroker("amqp://guest:guest@localhost:5672/")
```

**Kafka:**
```python
from faststream.kafka import KafkaBroker
broker = KafkaBroker("localhost:9092")
```

### FastStream Worker Configuration

Configure FastStream worker with custom options:

```python
app.add_faststream_worker(
    "message_processor",
    faststream_app,
    log_level=logging.DEBUG,  # Custom log level
    # Additional FastStream options can be passed here
)
```

### Best Practices for FastStream Integration

1. **Use Pydantic models**: Define message schemas with Pydantic for validation
2. **Error handling**: Handle errors in message consumers gracefully
3. **Idempotency**: Make message processing idempotent when possible
4. **Workflow orchestration**: Use Temporal workflows for complex processing
5. **Message filtering**: Use FastStream filtering for routing messages
6. **Dead-letter queues**: Implement dead-letter queues for failed messages
7. **Monitoring**: Monitor message processing rates and errors

### FastStream Producer Example

Publish messages to queues:

```python
from faststream import FastStream
from faststream.redis import RedisBroker

broker = RedisBroker("redis://localhost:6379")
app = FastStream(broker)

async def publish_order(order_data: dict):
    """Publish order message."""
    await broker.publish(order_data, "orders")

# Use in your application
asyncio.run(publish_order({"order_id": "123", "total": 99.99}))
```

## Best Practices

### Application Structure

1. **Separate concerns**: Keep activities, workflows, and configuration in separate files
2. **Use modules**: Organize code into logical modules
3. **Environment configuration**: Use environment variables for all configuration
4. **Type hints**: Use type hints throughout for better IDE support

### Worker Organization

1. **One worker per queue**: Each task queue should have dedicated workers
2. **Group related workers**: Put related activities/workflows in the same worker
3. **Separate concerns**: Keep different business domains in separate workers
4. **Resource limits**: Set appropriate concurrency limits per worker

### Error Handling

1. **Activity retries**: Configure retry policies for activities
2. **Workflow timeouts**: Set appropriate timeouts for workflow execution
3. **Error propagation**: Handle errors appropriately in workflows
4. **Logging**: Log errors with context for debugging

### Performance

1. **Activity concurrency**: Tune `TEMPORAL_MAX_CONCURRENT_ACTIVITIES`
2. **Workflow concurrency**: Tune `TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS`
3. **Task queue separation**: Use separate queues for different workloads
4. **Monitoring**: Enable Prometheus metrics for observability

### Security

1. **TLS**: Enable TLS for production Temporal connections
2. **API keys**: Use API keys for Temporal Cloud or secured clusters
3. **Secrets**: Store sensitive data in environment variables or secret managers
4. **Validation**: Validate all inputs in activities and workflows
