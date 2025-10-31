# Advanced Usage

This guide covers advanced patterns, customization options, and techniques for power users of Temporal-boost.

## Table of Contents

- [Custom Runtime Configuration](#custom-runtime-configuration)
- [Worker Customization](#worker-customization)
- [Interceptors](#interceptors)
- [Custom Logging](#custom-logging)
- [Multiple Clients](#multiple-clients)
- [Worker Lifecycle](#worker-lifecycle)
- [Error Handling Patterns](#error-handling-patterns)
- [Performance Optimization](#performance-optimization)

## Custom Runtime Configuration

Configure Temporal runtime with custom telemetry and metrics:

```python
from temporal_boost import BoostApp
from temporalio.runtime import LoggingConfig, PrometheusConfig, Runtime

app = BoostApp("advanced-app")

worker = app.add_worker("custom_worker", "custom_queue", activities=[...])

# Configure custom runtime
worker.configure_temporal_runtime(
    prometheus_bind_address="0.0.0.0:9090",
    prometheus_counters_total_suffix=True,
    prometheus_unit_suffix=True,
    prometheus_durations_as_seconds=True,
    global_tags={"environment": "production", "service": "my-service"},
    attach_service_name=True,
    metric_prefix="temporal_boost",
)
```

### Custom Logging Configuration

```python
import logging
import logging.config
from temporal_boost import BoostApp

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json": {
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "detailed",
            "level": "INFO",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "temporal.log",
            "maxBytes": 10485760,
            "backupCount": 5,
            "formatter": "json",
            "level": "DEBUG",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"],
    },
}

app = BoostApp(logger_config=LOGGING_CONFIG)
```

## Worker Customization

### Per-Worker Configuration

Customize individual workers with specific settings:

```python
worker = app.add_worker(
    "high_throughput_worker",
    "high_throughput_queue",
    activities=[...],
    max_concurrent_activities=1000,
    max_concurrent_workflow_tasks=500,
)

# Configure client
worker.configure_temporal_client(
    target_host="temporal.example.com:7233",
    namespace="production",
    use_pydantic_data_converter=True,
)

# Configure runtime
worker.configure_temporal_runtime(
    prometheus_bind_address="0.0.0.0:9091",
)
```

### Worker Builder Pattern

Use builders directly for maximum control:

```python
from temporal_boost.temporal.client import TemporalClientBuilder
from temporal_boost.temporal.runtime import TemporalRuntimeBuilder
from temporal_boost.temporal.worker import TemporalWorkerBuilder
from temporal_boost.workers.temporal import TemporalBoostWorker

# Build custom client
client_builder = TemporalClientBuilder(
    target_host="custom-host:7233",
    namespace="custom-namespace",
    use_pydantic_data_converter=True,
)

# Build custom runtime
runtime_builder = TemporalRuntimeBuilder(
    prometheus_bind_address="0.0.0.0:9090",
    global_tags={"custom": "tag"},
)

# Build custom worker
worker_builder = TemporalWorkerBuilder(
    task_queue="custom_queue",
    max_concurrent_activities=200,
    max_concurrent_workflow_tasks=100,
)

# Create worker
client = await client_builder.build()
runtime = runtime_builder.build()
worker_builder.set_client(client)
worker = worker_builder.build()
```

## Interceptors

Interceptors allow you to add cross-cutting concerns like logging, metrics, or authentication.

### Creating an Interceptor

```python
from temporalio.worker import ExecuteActivityInput, ExecuteWorkflowInput
from temporalio.worker.interceptor import (
    ActivityInboundInterceptor,
    ActivityInterceptor,
    WorkflowInboundInterceptor,
    WorkflowInterceptor,
)

class LoggingActivityInterceptor(ActivityInterceptor):
    def intercept_activity(
        self, next: ActivityInboundInterceptor
    ) -> ActivityInboundInterceptor:
        return LoggingActivityInboundInterceptor(next)

class LoggingActivityInboundInterceptor(ActivityInboundInterceptor):
    def __init__(self, next_inbound: ActivityInboundInterceptor):
        self._next = next_inbound

    async def execute_activity(self, input: ExecuteActivityInput) -> Any:
        logger.info(f"Executing activity: {input.func}")
        try:
            result = await self._next.execute_activity(input)
            logger.info(f"Activity completed: {input.func}")
            return result
        except Exception as e:
            logger.error(f"Activity failed: {input.func}, error: {e}")
            raise

class LoggingWorkflowInterceptor(WorkflowInterceptor):
    def intercept_workflow(
        self, next: WorkflowInboundInterceptor
    ) -> WorkflowInboundInterceptor:
        return LoggingWorkflowInboundInterceptor(next)

class LoggingWorkflowInboundInterceptor(WorkflowInboundInterceptor):
    def __init__(self, next_inbound: WorkflowInboundInterceptor):
        self._next = next_inbound

    def execute_workflow(self, input: ExecuteWorkflowInput) -> Any:
        logger.info(f"Executing workflow: {input.workflow_class}")
        return self._next.execute_workflow(input)
```

### Using Interceptors

```python
from temporalio.worker._interceptor import Interceptor

app = BoostApp("interceptor-example")

interceptor = Interceptor(
    activity_interceptor=LoggingActivityInterceptor(),
    workflow_interceptor=LoggingWorkflowInterceptor(),
)

worker = app.add_worker(
    "logged_worker",
    "logged_queue",
    activities=[my_activity],
    workflows=[my_workflow],
    interceptors=[interceptor],
)
```

## Custom Logging

### Structured Logging with Context

```python
import logging
import logging.config
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

class ContextualFormatter(logging.Formatter):
    def format(self, record):
        record.request_id = request_id_var.get()
        return super().format(record)

logging_config = {
    "version": 1,
    "formatters": {
        "contextual": {
            "()": ContextualFormatter,
            "format": "%(asctime)s [%(levelname)s] [%(request_id)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "contextual",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}

app = BoostApp(logger_config=logging_config)
```

### Activity Logging Decorator

```python
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def log_activity(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger.info(f"Starting activity: {func.__name__}")
        try:
            result = await func(*args, **kwargs)
            logger.info(f"Completed activity: {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"Failed activity: {func.__name__}, error: {e}")
            raise
    return wrapper

@activity.defn(name="logged_activity")
@log_activity
async def my_activity(data: str) -> str:
    return f"Processed: {data}"
```

## Multiple Clients

### Multiple Temporal Clusters

```python
app = BoostApp("multi-cluster")

# Worker 1: Production cluster
worker1 = app.add_worker("prod_worker", "prod_queue", activities=[...])
worker1.configure_temporal_client(
    target_host="prod.temporal.example.com:7233",
    namespace="production",
)

# Worker 2: Staging cluster
worker2 = app.add_worker("staging_worker", "staging_queue", activities=[...])
worker2.configure_temporal_client(
    target_host="staging.temporal.example.com:7233",
    namespace="staging",
)
```

## Worker Lifecycle

### Custom Worker Shutdown

```python
import signal
import sys

app = BoostApp("lifecycle-example")

def signal_handler(sig, frame):
    logger.info("Received shutdown signal")
    # Custom cleanup logic here
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

worker = app.add_worker("lifecycle_worker", "lifecycle_queue", activities=[...])

# Custom shutdown hook
async def custom_shutdown():
    logger.info("Performing custom cleanup")
    # Your cleanup logic

# Note: Temporal-boost handles graceful shutdown automatically
```

## Error Handling Patterns

### Activity Retry with Custom Logic

```python
from temporalio import activity
from temporalio.common import RetryPolicy
from datetime import timedelta

@activity.defn(
    name="retryable_activity",
    start_to_close_timeout=timedelta(minutes=5),
    retry_policy=RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=60),
        maximum_attempts=3,
    ),
)
async def retryable_activity(data: str) -> str:
    try:
        # Your logic here
        return process_data(data)
    except TransientError:
        # Will be retried automatically
        raise
    except PermanentError:
        # Will not be retried
        raise
```

### Workflow Error Handling

```python
from temporalio import workflow
from temporalio.exceptions import ActivityError, ApplicationError

@workflow.defn(sandboxed=False, name="ErrorHandlingWorkflow")
class ErrorHandlingWorkflow:
    @workflow.run
    async def run(self, data: str) -> dict:
        try:
            result = await workflow.execute_activity(
                risky_activity,
                data,
                task_queue="error_queue",
                start_to_close_timeout=timedelta(minutes=5),
            )
            return {"status": "success", "result": result}
        except ActivityError as e:
            # Activity failed
            workflow.logger.error(f"Activity failed: {e}")
            return {"status": "failed", "error": str(e)}
        except ApplicationError as e:
            # Application-specific error
            workflow.logger.error(f"Application error: {e}")
            raise
```

## Performance Optimization

### Tuning Concurrency

```python
# High-throughput worker
high_throughput_worker = app.add_worker(
    "high_throughput",
    "high_throughput_queue",
    activities=[...],
    max_concurrent_activities=1000,
    max_concurrent_workflow_tasks=500,
    max_concurrent_activity_task_polls=50,
    max_concurrent_workflow_task_polls=50,
)

# Low-latency worker
low_latency_worker = app.add_worker(
    "low_latency",
    "low_latency_queue",
    activities=[...],
    max_concurrent_activities=100,
    max_concurrent_workflow_tasks=50,
    nonsticky_to_sticky_poll_ratio=0.1,  # Prefer sticky workflows
)
```

### Sticky Workflows

Sticky workflows keep workflow state in memory, improving performance:

```python
# High sticky ratio for better performance
worker.configure_temporal_runtime(
    # Worker polls are configured at worker level
)

# In worker configuration
worker = app.add_worker(
    "sticky_worker",
    "sticky_queue",
    workflows=[MyWorkflow],
    nonsticky_to_sticky_poll_ratio=0.1,  # 10% non-sticky, 90% sticky
)
```

### Connection Pooling

Temporal SDK handles connection pooling automatically, but you can optimize:

```python
# Multiple workers share the same runtime (default)
# For better resource usage, configure shared runtime

runtime_builder = TemporalRuntimeBuilder(
    prometheus_bind_address="0.0.0.0:9090",
)

runtime = runtime_builder.build()

# Use same runtime for multiple workers
worker1 = app.add_worker("worker1", "queue1", activities=[...])
worker1.configure_temporal_client(...)
# Runtime is shared automatically
```

### Activity Result Caching

For expensive activities that can be cached:

```python
from functools import lru_cache
from temporalio import activity

# Cache at activity level (use with caution)
@activity.defn(name="cached_activity")
async def cached_activity(key: str) -> str:
    return expensive_operation(key)

# Or implement caching in workflow
@workflow.defn(sandboxed=False, name="CachedWorkflow")
class CachedWorkflow:
    def __init__(self):
        self._cache: dict[str, str] = {}

    @workflow.run
    async def run(self, key: str) -> str:
        if key in self._cache:
            return self._cache[key]
        
        result = await workflow.execute_activity(
            cached_activity,
            key,
            task_queue="cache_queue",
            start_to_close_timeout=timedelta(minutes=5),
        )
        self._cache[key] = result
        return result
```

## Advanced Patterns

### Workflow Versioning

```python
@workflow.defn(sandboxed=False, name="VersionedWorkflow")
class VersionedWorkflow:
    @workflow.run
    async def run(self, data: dict) -> dict:
        version = data.get("version", 1)
        
        if version == 1:
            return await self._run_v1(data)
        elif version == 2:
            return await self._run_v2(data)
        else:
            raise ValueError(f"Unsupported version: {version}")
    
    async def _run_v1(self, data: dict) -> dict:
        # V1 logic
        pass
    
    async def _run_v2(self, data: dict) -> dict:
        # V2 logic
        pass
```

### Custom Data Converter

```python
from temporalio.converter import DataConverter, PayloadCodec
from temporal_boost.temporal.client import TemporalClientBuilder

class CustomPayloadCodec(PayloadCodec):
    def encode(self, payloads: list[Payload]) -> list[Payload]:
        # Custom encoding logic
        return payloads
    
    def decode(self, payloads: list[Payload]) -> list[Payload]:
        # Custom decoding logic
        return payloads

custom_converter = DataConverter(
    payload_converter=DefaultPayloadConverter(),
    payload_codec=CustomPayloadCodec(),
)

client_builder = TemporalClientBuilder()
client_builder.set_kwargs(data_converter=custom_converter)
```

These advanced patterns provide powerful customization options for complex use cases. For more examples, see [Examples](examples.md).

