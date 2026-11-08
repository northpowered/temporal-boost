# Advanced Usage

This guide covers advanced patterns, customization options, and techniques for power users of Temporal-boost.

## Table of Contents

- [Custom Runtime Configuration](#custom-runtime-configuration)
- [Metrics Across Workers and Processes](#metrics-across-workers-and-processes)
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

# Fragment inside an async function: build and attach the runtime before connecting
runtime = runtime_builder.build()
client_builder.set_runtime(runtime)
client = await client_builder.build()
worker_builder.set_client(client)
worker = worker_builder.build()
```

## Metrics Across Workers and Processes

Each `TemporalBoostWorker` owns an independent SDK runtime and client. There is **no automatic
runtime sharing**. A Prometheus exporter belongs to that runtime and binds its own listening socket.
The supported topology is a distinct endpoint for every concurrently running worker runtime, scraped
individually by Prometheus. SDK `OpenTelemetryConfig` can instead send each runtime's metrics to an
external collector configured by your deployment.

| Deployment | Exporter endpoints to scrape |
| --- | --- |
| Two workers in one process | Two distinct addresses, for example `:9100` and `:9101` |
| Two processes, each running two workers on one host | Four distinct addresses, for example `:9100` through `:9103` |
| Two pods/containers, each running two workers | Both ports in each pod/container, for example `pod-a:9100`, `pod-a:9101`, `pod-b:9100`, `pod-b:9101` |

Configure each worker before starting it or accessing `temporal_client_runtime`. This fragment assumes
`payments` and `notifications` were returned by `app.add_worker(...)`:

```python
payments.configure_temporal_runtime(
    prometheus_bind_address="0.0.0.0:9100",
    global_tags={"boost_worker": "payments"},
)
notifications.configure_temporal_runtime(
    prometheus_bind_address="0.0.0.0:9101",
    global_tags={"boost_worker": "notifications"},
)
```

The default `TEMPORAL_PROMETHEUS_BIND_ADDRESS` is applied to each worker, so one fixed address is
appropriate for a single runtime. Override it per worker when starting more than one. For processes
sharing a network address, allocate separate port ranges. The external `--workers N` launcher repeats
the application configuration; it does not allocate metrics ports or aggregate SDK metrics. Prefer
separate processes with explicit port ranges, or pods with separate network addresses. Scrape each
worker endpoint in every replica using static targets or service discovery.

The runnable [metrics example](https://github.com/northpowered/temporal-boost/blob/main/examples/example_metrics.py)
has two workers. With a reachable Temporal server, start two processes in separate terminals:

```bash
METRICS_BASE_PORT=9100 uv run python examples/example_metrics.py run all
METRICS_BASE_PORT=9102 uv run python examples/example_metrics.py run all
```

`METRICS_BASE_PORT` is an environment variable implemented by this example. It is not a Temporal-boost
configuration option. A Prometheus server on the same host can scrape all four exporters:

```yaml
scrape_configs:
  - job_name: temporal-workers
    metrics_path: /metrics
    static_configs:
      - targets: ["127.0.0.1:9100", "127.0.0.1:9101", "127.0.0.1:9102", "127.0.0.1:9103"]
```

Keep Prometheus's `instance` label to distinguish endpoints before aggregating across replicas.
Native worker metrics carry task queue labels. In the locked SDK, `global_tags` appear as resource
metadata in `target_info`; they are not automatically labels on every counter. Scrape `target_info`
alongside the metrics, and join it on `job`/`instance` when resource metadata is needed.

**Ownership and failure:** runtimes are built lazily in the worker's process. The worker passes its
runtime to its own client. Cleanup releases worker/client/runtime references; the SDK manages native
handles and provides no public `Runtime.close()` in the locked version. External runtime or metric
meter references can extend the exporter's lifetime. Do not build a live SDK runtime in a parent and
transfer it to a child: SDK runtimes do not work across forks. There is no shared-runtime API here.

An exporter initialization failure now propagates and fails worker startup, including a bind conflict.
The log names the actual configured Prometheus endpoint; telemetry is never retried with metrics
disabled. `run all` then stops peer workers, and the external supervisor propagates the failure.
Configure distinct endpoints rather than relying on the first runtime that happens to bind.

**Migration:** older releases could continue with metrics disabled after a port conflict, leaving a
partially observed service. Such deployments now fail startup. Give every runtime a unique endpoint
or use an external telemetry collector. An explicit `metrics=PrometheusConfig(...)` takes priority over
`prometheus_bind_address`, and follows the same failure policy.

`PROMETHEUS_MULTIPROC_DIR` is unrelated to the SDK exporter. It is used by Python's `prometheus_client`
multiprocess mode when that client is installed and configured separately. Temporal's SDK exporter
does not write there, and Temporal-boost does not combine SDK metrics through it. The launcher's legacy
directory setup is not an aggregator; its cleanup/removal is tracked separately in TB-028.

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
import asyncio

from temporal_boost import AsyncBoostWorker, BoostApp


class ServiceWorker(AsyncBoostWorker):
    def __init__(self) -> None:
        super().__init__()
        self.name = "service"
        self.finished: asyncio.Event | None = None

    async def run_async(self) -> None:
        # Create loop-bound resources here.
        self.finished = asyncio.Event()
        await self.finished.wait()

    async def shutdown(self) -> None:
        # Close resources here, on the loop that created them.
        # This must also be safe during partial startup.
        if self.finished is not None:
            self.finished.set()


app = BoostApp("lifecycle-example", shutdown_timeout=30.0)
app.add_async_runtime("service", ServiceWorker())

if __name__ == "__main__":
    app.run()
```

Run this example with `python main.py run all`. `AsyncBoostWorker` implements `run()` and the
thread-safe `request_stop()`; keep those implementations and override `run_async()` and `shutdown()`.
Cleanup runs once per invocation, including when `run_async()` returns normally. It must tolerate
partially initialized resources and make `run_async()` return. A stop requested before the loop
starts is remembered. Successful sequential runs create fresh loops; concurrent runs are rejected.
In `run all`, an exception or a normal return before application shutdown stops the other workers
and propagates as a failure. Finite workers must call `app.stop()` before returning to finish normally,
or be run individually. The first failure remains primary if peer cleanup fails or times out.
For `AsyncBoostWorker`, an error in `run_async()` survives its own cleanup failure too; cleanup errors
during cancellation propagate instead of being mistaken for normal cancellation.
Calling async `shutdown()` directly is reserved for code already running on the owning loop.
For another threading or loop model, implement `BaseBoostWorker.request_stop()` using that model's
thread-safe signaling API. The [shutdown guide](running_application.md#graceful-shutdown) describes
deadlines and current adapter limitations.

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

SDK clients manage their connections internally. Temporal-boost workers create independent clients
and runtimes; configuring a builder or creating a standalone runtime does not share it with those
workers. For standalone builders, call `client_builder.set_runtime(runtime)` before `await build()`.
For multiple Temporal-boost workers, follow the
[metrics endpoint topology](#metrics-across-workers-and-processes).

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

