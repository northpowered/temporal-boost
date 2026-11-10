# FastStream Integration

FastStream is a modern framework for building async message consumers and producers. Temporal-boost provides seamless integration with FastStream, allowing you to combine event-driven architectures with Temporal workflows.

## Overview

FastStream integration allows you to:
- **Consume messages** from message queues (Redis, RabbitMQ, Kafka, etc.)
- **Trigger Temporal workflows** from message events
- **Process events** asynchronously with reliable execution
- **Combine event-driven** and workflow-based architectures

## Installation

Install Temporal-boost with FastStream support:

```bash
pip install "temporal-boost[faststream]"
```

This installs FastStream and its dependencies (including `anyio`).

## Quick Start

### Basic Example

```python
from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel
from temporal_boost import BoostApp

# Message model
class TaskMessage(BaseModel):
    task_id: str
    description: str
    priority: int

# Initialize FastStream
broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("tasks")
async def process_task(message: TaskMessage):
    """Process task messages."""
    logger.info(f"Processing task: {message.task_id}")

# Initialize Temporal-boost
app = BoostApp("faststream-example")

# Register FastStream worker
app.add_faststream_worker("message_processor", faststream_app)

if __name__ == "__main__":
    app.run()
```

## Integration Patterns

### Pattern 1: Message Queue → Temporal Workflow

Trigger Temporal workflows from message queue events:

```python
from faststream import FastStream
from faststream.redis import RedisBroker
from temporalio.client import Client
from temporal_boost import BoostApp

broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("orders")
async def handle_order(message: OrderMessage):
    """Handle order message and start workflow."""
    client = await Client.connect("localhost:7233")
    
    await client.start_workflow(
        "OrderWorkflow",
        message.dict(),
        id=f"order-{message.order_id}",
        task_queue="order_queue",
    )

app = BoostApp("order-service")
app.add_worker("order_worker", "order_queue", workflows=[OrderWorkflow])
app.add_faststream_worker("message_processor", faststream_app)
```

### Pattern 2: Multiple Message Queues

Handle multiple message queues with different handlers:

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

@broker.subscriber("emails")
async def handle_emails(message: EmailMessage):
    """Handle email messages."""
    # Process emails...

app.add_faststream_worker("message_processor", faststream_app)
```

### Pattern 3: Conditional Processing

Route messages based on content:

```python
@broker.subscriber("tasks")
async def handle_task(message: TaskMessage):
    """Handle tasks with conditional routing."""
    if message.priority > 5:
        # High priority: execute immediately
        await process_high_priority_task(message)
    else:
        # Normal priority: start workflow
        client = await Client.connect("localhost:7233")
        await client.start_workflow(
            "TaskWorkflow",
            message.dict(),
            task_queue="task_queue",
        )
```

## Supported Brokers

FastStream supports multiple message brokers:

### Redis

```python
from faststream.redis import RedisBroker

broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)
```

### RabbitMQ

```python
from faststream.rabbit import RabbitBroker

broker = RabbitBroker("amqp://guest:guest@localhost:5672/")
faststream_app = FastStream(broker)
```

### Kafka

```python
from faststream.kafka import KafkaBroker

broker = KafkaBroker("localhost:9092")
faststream_app = FastStream(broker)
```

## Configuration

### Worker Configuration

Configure FastStream worker with custom options:

```python
app.add_faststream_worker(
    "message_processor",
    faststream_app,
    log_level=logging.DEBUG,  # Custom log level
    region="west",  # Passed to startup hooks and the lifespan context
)
```

### Managed Shutdown

FastStream workers support `app.stop()` when launched through `run all`. The coordinator requests
stop and waits up to `BoostApp(shutdown_timeout=...)` for cleanup. You can also retain the worker
returned by `add_faststream_worker()` and call its thread-safe `worker.request_stop()`, including
during startup. Repeated requests are safe.

The adapter uses FastStream's public `start()` and `stop()` methods and its lifespan context on
one owning event loop. Pending startup is cancelled and joined before shutdown hooks and broker
cleanup run. Startup and cleanup failures propagate to the caller; a cleanup failure does not
replace an earlier startup failure. If a shutdown hook fails before the broker closes, the adapter
also attempts the broker's public `stop()` method.

Async `worker.shutdown()` waits for cleanup on the owning loop and is harmless before or after
a run. From another thread or loop, or inside a lifecycle hook, use `worker.request_stop()`.
Cancellation of one shutdown waiter does not cancel cleanup. A broker or hook that never finishes
can exceed the coordinator's shutdown budget.

The lifecycle and option forwarding are verified against FastStream **0.5.48**, the lockfile version,
using an in-memory broker. Its existing `run(log_level, options)` signature accepts the positional
options mapping. The adapter now manages the lifecycle directly because `FastStream.run()` installs
signal handlers that cannot be installed in a `run all` worker thread. Startup options still reach
startup hooks and the lifespan context. Code using `FastStream.exit()` or overriding `FastStream.run()`
should move its stop requests to `worker.request_stop()` and initialization/cleanup to lifecycle hooks.
For an individual worker running on the main thread, the adapter handles SIGINT/SIGTERM and restores
the previous handlers after cleanup.

### Message Broker Configuration

Configure broker connection:

```python
# Redis with authentication
broker = RedisBroker("redis://user:password@localhost:6379")

# Redis with custom settings
broker = RedisBroker(
    "redis://localhost:6379",
    max_connections=10,
    socket_keepalive=True,
)

# RabbitMQ with custom settings
broker = RabbitBroker(
    "amqp://guest:guest@localhost:5672/",
    max_connections=10,
    virtualhost="/",
)
```

## Error Handling

### Message Processing Errors

Handle errors in message consumers:

```python
@broker.subscriber("orders")
async def handle_order(message: OrderMessage):
    """Handle order with error handling."""
    try:
        client = await Client.connect("localhost:7233")
        await client.start_workflow(
            "OrderWorkflow",
            message.dict(),
            task_queue="order_queue",
        )
    except Exception as e:
        logger.error(f"Failed to process order {message.order_id}: {e}")
        # Optionally publish to dead-letter queue
        await broker.publish(message.dict(), "orders-dlq")
        raise
```

### Dead-Letter Queues

Implement dead-letter queues for failed messages:

```python
@broker.subscriber("orders")
async def handle_order(message: OrderMessage):
    """Handle order with DLQ support."""
    try:
        # Process message...
        pass
    except Exception:
        # Publish to dead-letter queue
        await broker.publish(message.dict(), "orders-dlq")
        raise
```

## Best Practices

1. **Use Pydantic Models**: Define message schemas for type safety and validation
2. **Idempotency**: Make message processing idempotent when possible
3. **Error Handling**: Always handle errors gracefully with retries or DLQ
4. **Workflow Orchestration**: Use Temporal workflows for complex processing
5. **Message Filtering**: Use FastStream filtering for routing messages
6. **Monitoring**: Monitor message processing rates and errors
7. **Resource Limits**: Set appropriate concurrency limits for message processing

## Examples

See the [examples directory](https://github.com/northpowered/temporal-boost/tree/main/examples) for comprehensive FastStream examples:

- `example_simple_faststream.py` - Basic FastStream integration
- `example_faststream_temporal.py` - FastStream with Temporal workflows
- `example_faststream_advanced.py` - Advanced patterns and error handling
- `example_faststream_producer.py` - Message producer example

## Additional Resources

- [FastStream Documentation](https://faststream.airt.ai/)
- [Temporal-boost Examples](https://github.com/northpowered/temporal-boost/tree/main/examples)
- [Creating Applications Guide](creating_application.md#faststream-workers)

