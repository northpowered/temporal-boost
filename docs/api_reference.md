# API Reference

Complete API reference for Temporal-boost.

## BoostApp

Main application class for Temporal-boost.

### `BoostApp.__init__()`

Initialize a BoostApp instance.

```python
BoostApp(
    name: str | None = None,
    *,
    temporal_endpoint: str | None = None,
    temporal_namespace: str | None = None,
    debug_mode: bool = False,
    use_pydantic: bool | None = None,
    logger_config: dict[str, Any] | str | Path | None = DEFAULT_LOGGING_CONFIG,
) -> None
```

**Parameters:**

- `name` (str | None): Application name. Defaults to "temporal_generic_service".
- `temporal_endpoint` (str | None): Override `TEMPORAL_TARGET_HOST` environment variable.
- `temporal_namespace` (str | None): Override `TEMPORAL_NAMESPACE` environment variable.
- `debug_mode` (bool): Enable debug mode. Defaults to False.
- `use_pydantic` (bool | None): Override `TEMPORAL_USE_PYDANTIC_DATA_CONVERTER` environment variable.
- `logger_config` (dict | str | Path | None): Logging configuration. Can be a dict, path to JSON/YAML file, or path to logging config file.

**Example:**

```python
app = BoostApp(
    name="my-service",
    temporal_endpoint="localhost:7233",
    temporal_namespace="default",
    use_pydantic=True,
)
```

### `BoostApp.add_worker()`

Add a Temporal worker to the application.

```python
add_worker(
    worker_name: str,
    task_queue: str,
    *,
    activities: list[Callable[..., Any]] | None = None,
    workflows: list[type] | None = None,
    interceptors: list[Interceptor] | None = None,
    cron_schedule: str | None = None,
    cron_runner: MethodAsyncNoParam[Any, Any] | None = None,
    **worker_kwargs: Any,
) -> TemporalBoostWorker
```

**Parameters:**

- `worker_name` (str): Unique worker name. Cannot be reserved names: "run", "cron", "exec", "all".
- `task_queue` (str): Temporal task queue name.
- `activities` (list[Callable] | None): List of activity functions.
- `workflows` (list[type] | None): List of workflow classes.
- `interceptors` (list[Interceptor] | None): List of Temporal interceptors.
- `cron_schedule` (str | None): CRON schedule string for scheduled workflows.
- `cron_runner` (MethodAsyncNoParam | None): Workflow run method for CRON workers.
- `**worker_kwargs`: Additional worker configuration options.

**Returns:**

- `TemporalBoostWorker`: The created worker instance.

**Example:**

```python
worker = app.add_worker(
    "my_worker",
    "my_queue",
    activities=[my_activity],
    workflows=[MyWorkflow],
)
```

### `BoostApp.add_asgi_worker()`

Add an ASGI application as a worker.

```python
add_asgi_worker(
    worker_name: str,
    asgi_app: Any,
    host: str,
    port: int,
    *,
    log_level: str | int | None = None,
    asgi_worker_type: ASGIWorkerType = ASGIWorkerType.auto,
    **asgi_worker_kwargs: Any,
) -> None
```

**Parameters:**

- `worker_name` (str): Unique worker name.
- `asgi_app` (Any): ASGI application instance or string path to ASGI app.
- `host` (str): Host to bind to.
- `port` (int): Port to bind to.
- `log_level` (str | int | None): Logging level for ASGI server.
- `asgi_worker_type` (ASGIWorkerType): ASGI server type (auto, uvicorn, hypercorn, granian).
- `**asgi_worker_kwargs`: Additional ASGI worker options.

**Example:**

```python
from fastapi import FastAPI

fastapi_app = FastAPI()
app.add_asgi_worker("api_worker", fastapi_app, "0.0.0.0", 8000)
```

### `BoostApp.add_faststream_worker()`

Add a FastStream application as a worker.

```python
add_faststream_worker(
    worker_name: str,
    faststream_app: Any,
    *,
    log_level: str | int | None = None,
    **faststream_kwargs: Any,
) -> FastStreamBoostWorker
```

**Parameters:**

- `worker_name` (str): Unique worker name.
- `faststream_app` (Any): FastStream application instance.
- `log_level` (str | int | None): Logging level.
- `**faststream_kwargs`: Additional FastStream options.

**Returns:**

- `FastStreamBoostWorker`: The created FastStream worker instance.

**Example:**

```python
from faststream import FastStream

faststream_app = FastStream(broker)
app.add_faststream_worker("message_worker", faststream_app)
```

### `BoostApp.run()`

Run the application CLI.

```python
run(*args: Any, **kwargs: Any) -> None
```

**Example:**

```python
if __name__ == "__main__":
    app.run()
```

### `BoostApp.get_registered_workers()`

Get list of all registered workers.

```python
get_registered_workers() -> list[BaseBoostWorker]
```

**Returns:**

- `list[BaseBoostWorker]`: List of registered workers.

## TemporalBoostWorker

Temporal worker class.

### `TemporalBoostWorker.configure_temporal_client()`

Configure Temporal client for the worker.

```python
configure_temporal_client(
    *,
    target_host: str | None = None,
    namespace: str | None = None,
    api_key: str | None = None,
    identity: str | None = None,
    tls: bool | None = None,
    use_pydantic_data_converter: bool | None = None,
    **kwargs: Any,
) -> None
```

**Parameters:**

- `target_host` (str | None): Temporal server address.
- `namespace` (str | None): Temporal namespace.
- `api_key` (str | None): API key for Temporal Cloud.
- `identity` (str | None): Client identity.
- `tls` (bool | None): Enable TLS.
- `use_pydantic_data_converter` (bool | None): Use Pydantic data converter.
- `**kwargs`: Additional client options.

**Example:**

```python
worker.configure_temporal_client(
    target_host="temporal.example.com:7233",
    namespace="production",
    use_pydantic_data_converter=True,
)
```

### `TemporalBoostWorker.configure_temporal_runtime()`

Configure Temporal runtime for the worker.

```python
configure_temporal_runtime(
    *,
    logging: LoggingConfig | None = None,
    metrics: OpenTelemetryConfig | PrometheusConfig | MetricBuffer | None = None,
    global_tags: Mapping[str, str] | None = None,
    attach_service_name: bool = True,
    metric_prefix: str | None = None,
    prometheus_bind_address: str | None = config.PROMETHEUS_BIND_ADDRESS,
    prometheus_counters_total_suffix: bool | None = config.PROMETHEUS_COUNTERS_TOTAL_SUFFIX,
    prometheus_unit_suffix: bool | None = config.PROMETHEUS_UNIT_SUFFIX,
    prometheus_durations_as_seconds: bool | None = config.PROMETHEUS_DURATIONS_AS_SECONDS,
) -> None
```

**Parameters:**

- `logging` (LoggingConfig | None): Custom logging configuration.
- `metrics` (OpenTelemetryConfig | PrometheusConfig | MetricBuffer | None): Metrics configuration.
- `global_tags` (Mapping[str, str] | None): Global tags for metrics.
- `attach_service_name` (bool): Attach service name to metrics.
- `metric_prefix` (str | None): Prefix for metric names.
- `prometheus_bind_address` (str | None): Prometheus metrics bind address.
- `prometheus_counters_total_suffix` (bool | None): Append `_total` to counters.
- `prometheus_unit_suffix` (bool | None): Append unit suffix to metrics.
- `prometheus_durations_as_seconds` (bool | None): Express durations in seconds.

**Example:**

```python
worker.configure_temporal_runtime(
    prometheus_bind_address="0.0.0.0:9090",
    global_tags={"environment": "production"},
)
```

### `TemporalBoostWorker.run()`

Run the worker.

```python
run() -> None
```

**Example:**

```python
worker.run()
```

### `TemporalBoostWorker.cron()`

Run the worker as a CRON worker.

```python
cron() -> None
```

**Example:**

```python
worker.cron()
```

### Properties

- `temporal_client` (Client): Get Temporal client instance.
- `temporal_worker` (Worker): Get Temporal worker instance.
- `temporal_cron_runner` (MethodAsyncNoParam): Get CRON runner method.

## TemporalClientBuilder

Builder for Temporal client configuration.

### `TemporalClientBuilder.__init__()`

```python
__init__(
    target_host: str | None = None,
    namespace: str | None = None,
    api_key: str | None = None,
    identity: str | None = None,
    *,
    tls: bool | None = None,
    use_pydantic_data_converter: bool | None = None,
    **kwargs: Any,
) -> None
```

### `TemporalClientBuilder.build()`

Build and return Temporal client.

```python
async def build() -> Client
```

**Returns:**

- `Client`: Temporal client instance.

## TemporalWorkerBuilder

Builder for Temporal worker configuration.

### `TemporalWorkerBuilder.__init__()`

```python
__init__(
    task_queue: str,
    *,
    debug_mode: bool = False,
    max_concurrent_workflow_tasks: int | None = None,
    max_concurrent_activities: int | None = None,
    max_concurrent_local_activities: int | None = None,
    max_concurrent_workflow_task_polls: int | None = None,
    nonsticky_to_sticky_poll_ratio: float | None = None,
    max_concurrent_activity_task_polls: int | None = None,
    **kwargs: Any,
) -> None
```

### `TemporalWorkerBuilder.build()`

Build and return Temporal worker.

```python
def build() -> Worker
```

**Returns:**

- `Worker`: Temporal worker instance.

## TemporalRuntimeBuilder

Builder for Temporal runtime configuration.

### `TemporalRuntimeBuilder.__init__()`

```python
__init__(
    *,
    logging: LoggingConfig | None = None,
    metrics: OpenTelemetryConfig | PrometheusConfig | MetricBuffer | None = None,
    global_tags: Mapping[str, str] | None = None,
    attach_service_name: bool = True,
    metric_prefix: str | None = None,
    prometheus_bind_address: str | None = config.PROMETHEUS_BIND_ADDRESS,
    prometheus_counters_total_suffix: bool | None = config.PROMETHEUS_COUNTERS_TOTAL_SUFFIX,
    prometheus_unit_suffix: bool | None = config.PROMETHEUS_UNIT_SUFFIX,
    prometheus_durations_as_seconds: bool | None = config.PROMETHEUS_DURATIONS_AS_SECONDS,
) -> None
```

### `TemporalRuntimeBuilder.build()`

Build and return Temporal runtime.

```python
def build() -> Runtime
```

**Returns:**

- `Runtime`: Temporal runtime instance.

## Enums

### `ASGIWorkerType`

ASGI worker server types.

- `auto`: Auto-detect available server
- `uvicorn`: Use Uvicorn server
- `hypercorn`: Use Hypercorn server
- `granian`: Use Granian server

## Configuration Constants

All configuration is available in `temporal_boost.temporal.config`:

- `TARGET_HOST`: Temporal server address
- `CLIENT_NAMESPACE`: Temporal namespace
- `CLIENT_TLS`: TLS enabled flag
- `CLIENT_API_KEY`: API key
- `CLIENT_IDENTITY`: Client identity
- `USE_PYDANTIC_DATA_CONVERTER`: Pydantic converter flag
- `MAX_CONCURRENT_WORKFLOW_TASKS`: Max concurrent workflow tasks
- `MAX_CONCURRENT_ACTIVITIES`: Max concurrent activities
- `MAX_CONCURRENT_LOCAL_ACTIVITIES`: Max concurrent local activities
- `MAX_WORKFLOW_TASK_POLLS`: Max workflow task polls
- `MAX_ACTIVITY_TASK_POLLS`: Max activity task polls
- `NONSTICKY_STICKY_RATIO`: Non-sticky to sticky ratio
- `GRACEFUL_SHUTDOWN_TIMEOUT`: Graceful shutdown timeout
- `PROMETHEUS_BIND_ADDRESS`: Prometheus bind address
- `PROMETHEUS_COUNTERS_TOTAL_SUFFIX`: Counters total suffix flag
- `PROMETHEUS_UNIT_SUFFIX`: Unit suffix flag
- `PROMETHEUS_DURATIONS_AS_SECONDS`: Durations as seconds flag

For detailed configuration options, see [Configuration Guide](configuration.md).

