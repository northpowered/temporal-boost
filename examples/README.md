# Temporal-boost Examples

This directory contains comprehensive examples demonstrating various features and use cases of Temporal-boost.

## Available Examples

### Basic Examples

- **`example_starter.py`** - Basic starter example
  - Simple activity and workflow
  - Worker registration
  - Run with: `python3 example_starter.py run all`

### Advanced Patterns

- **`example_cron.py`** - CRON worker example
  - Scheduled workflow execution
  - Daily report generation
  - Run with: `python3 example_cron.py cron daily_report`

- **`example_signals.py`** - Workflow signals example
  - Workflows waiting for external signals
  - Approval/rejection workflows
  - Run with: `python3 example_signals.py run approval_worker`
  - Use `example_client.py` to send signals

- **`example_parallel.py`** - Parallel activities example
  - Executing multiple activities concurrently
  - Using `asyncio.gather` for parallel execution
  - Run with: `python3 example_parallel.py run data_worker`

- **`example_error_handling.py`** - Error handling example
  - Custom retry policies
  - Activity heartbeat
  - Graceful error recovery
  - Run with: `python3 example_error_handling.py run worker`

### Real-World Scenarios

- **`example_ecommerce.py`** - E-commerce order processing
  - Complex multi-step workflow
  - Order validation, payment, fulfillment
  - Error handling and notifications
  - Run with: `python3 example_ecommerce.py run all`

- **`example_fastapi.py`** - FastAPI integration
  - Running FastAPI alongside Temporal workers
  - Starting workflows from HTTP endpoints
  - Querying workflow status via REST API
  - Run with: `python3 example_fastapi.py run all`
  - Access API at: `http://localhost:8000/docs`

### Integration Examples

- **`example_app.py`** - Comprehensive example
  - Multiple workers with different configurations
  - Pydantic models
  - ASGI worker integration
  - Prometheus metrics
  - Custom exec methods
  - Run with: `python3 example_app.py run all`

- **`example_asgi_app.py`** - Simple ASGI app
  - Basic FastAPI application
  - Used by other examples

- **`example_simple_faststream.py`** - Simple FastStream integration
  - Basic message queue consumer
  - Simple message processing
  - Run with: `python3 example_simple_faststream.py run message_processor`
  - Requires Redis: `docker run -p 6379:6379 redis:latest`

- **`example_faststream_temporal.py`** - FastStream with Temporal workflows
  - Message consumers that trigger workflows
  - Multiple message subscribers
  - Integration between event-driven architecture and Temporal
  - Run with: `python3 example_faststream_temporal.py run all`
  - Requires Redis: `docker run -p 6379:6379 redis:latest`

- **`example_faststream_advanced.py`** - Advanced FastStream patterns
  - Multiple message queues
  - Error handling and retries
  - Message filtering and routing
  - Producer/consumer patterns
  - Run with: `python3 example_faststream_advanced.py run message_processor`
  - Requires Redis: `docker run -p 6379:6379 redis:latest`

- **`example_faststream_producer.py`** - FastStream message producer
  - Publishing messages to queues
  - Testing FastStream consumers
  - Usage:
    ```bash
    python3 example_faststream_producer.py send_order <order_id> <customer_id>
    python3 example_faststream_producer.py send_task <task_id> <description> <priority>
    ```

### Client Examples

- **`example_client.py`** - Workflow client examples
  - Starting workflows
  - Sending signals
  - Querying workflow status
  - Getting workflow results
  - Usage examples:
    ```bash
    python3 example_client.py start_workflow greeting World
    python3 example_client.py start_workflow order order-123 customer-456
    python3 example_client.py send_signal <workflow_id> true "Approved"
    python3 example_client.py query_workflow <workflow_id>
    python3 example_client.py get_result <workflow_id>
    ```

## Running Examples

### Prerequisites

1. **Install Temporal-boost:**
   ```bash
   pip install temporal-boost
   ```

2. **Start Temporal server:**
   ```bash
   # Using Docker
   docker run -p 7233:7233 -p 8088:8088 temporalio/auto-setup:latest
   ```

3. **Set environment variables (optional):**
   ```bash
   export TEMPORAL_TARGET_HOST=localhost:7233
   export TEMPORAL_NAMESPACE=default
   ```

### Running a Worker

```bash
# Run all workers
python3 example_starter.py run all

# Run a specific worker
python3 example_starter.py run greeting_worker

# Run CRON worker
python3 example_cron.py cron daily_report
```

### Testing Workflows

1. **Start the worker:**
   ```bash
   python3 example_starter.py run greeting_worker
   ```

2. **Start a workflow (in another terminal):**
   ```bash
   python3 example_client.py start_workflow greeting World
   ```

## Example Structure

Each example follows a consistent structure:

```python
# 1. Imports
from temporal_boost import BoostApp
from temporalio import activity, workflow

# 2. Initialize app
app = BoostApp(name="example")

# 3. Define activities
@activity.defn(name="my_activity")
async def my_activity(...):
    ...

# 4. Define workflows
@workflow.defn(sandboxed=False, name="MyWorkflow")
class MyWorkflow:
    @workflow.run
    async def run(self, ...):
        ...

# 5. Register workers
app.add_worker("worker_name", "task_queue", activities=[...], workflows=[...])

# 6. Run application
if __name__ == "__main__":
    app.run()
```

## Learning Path

1. Start with **`example_starter.py`** to understand basics
2. Move to **`example_parallel.py`** for concurrent execution
3. Try **`example_error_handling.py`** for robust error handling
4. Explore **`example_ecommerce.py`** for real-world patterns
5. Integrate with **`example_fastapi.py`** for API integration

## Additional Resources

- [Full Documentation](https://northpowered.github.io/temporal-boost/)
- [Examples Guide](https://northpowered.github.io/temporal-boost/examples/)
- [API Reference](https://northpowered.github.io/temporal-boost/api_reference/)

