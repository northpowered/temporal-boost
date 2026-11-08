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
    shutdown_timeout: float = 30.0,
) -> None
```

**Parameters:**

- `name` (str | None): Application name. Defaults to "temporal_generic_service".
- `temporal_endpoint` (str | None): Override `TEMPORAL_TARGET_HOST` environment variable.
- `temporal_namespace` (str | None): Override `TEMPORAL_NAMESPACE` environment variable.
- `debug_mode` (bool): Enable debug mode. Defaults to False.
- `use_pydantic` (bool | None): `None` inherits `TEMPORAL_USE_PYDANTIC_DATA_CONVERTER`; `True` enables
  Pydantic and `False` disables automatic Pydantic selection. An explicit client `data_converter` takes priority.
- `logger_config` (dict | str | Path | None): Logging configuration. Can be a dict, path to JSON/YAML file, or path to logging config file.
- `shutdown_timeout` (float): Shared timeout in seconds for cooperative shutdown and joining worker threads.
  Must be finite and non-negative. Independent of Temporal SDK configuration.

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
    cron_workflow_id: str | None = None,
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
- `cron_workflow_id` (str | None): Stable workflow ID in the configured namespace. Defaults to
  `temporal-boost/cron/<percent-encoded task_queue>/<percent-encoded worker_name>`.
  Empty or whitespace-only explicit IDs raise `ValueError`.
- `**worker_kwargs`: Additional worker configuration options.

`cron_schedule` and `cron_runner` must be provided together or both omitted. Partial configuration,
or an explicitly empty/whitespace-only schedule, raises `ValueError` during worker construction before
connecting. Expression syntax is validated by the SDK/server. These rules also apply to direct
`TemporalBoostWorker` construction. Supplying `cron_workflow_id` alone does not enable CRON mode.
`add_worker()` registers commands locally; it does not create a server-side schedule.

`graceful_shutdown_timeout=timedelta(...)` in `worker_kwargs` sets the SDK activity grace period.
Omission or `None` inherits `TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT` (default 30 seconds), zero is preserved,
and negative durations raise `ValueError` at registration. This is independent of `BoostApp.shutdown_timeout`;
see [configuration](configuration.md#temporal_graceful_shutdown_timeout).

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
run(args: list[str] | None = None, **kwargs: Any) -> Any
```

`args` is one list of CLI arguments. Omission or `None` uses `sys.argv[1:]`; `[]` stays empty and triggers
the configured no-command help/usage behavior (code 2). Separate positional arguments and a single
command string are unsupported: use `app.run(["run", "worker_name"])`.

By default Typer raises `SystemExit`: help and successful commands use 0; unknown commands, missing
arguments, and invalid values use 2. Explicit nonzero exits are preserved. Unhandled worker errors
propagate and produce a nonzero process status. In `run all`, a worker's `SystemExit(0)` or
`SystemExit(None)` is converted to `RuntimeError` at the CLI boundary so coordinator failure cannot
report success; a direct `run_all_workers()` still raises the original exception.

Options such as `standalone_mode=False` and `prog_name="service"` are forwarded to Typer.
In non-standalone mode, `run()` returns the command's value and propagates parsing/worker exceptions
(for example, `click.UsageError` or `RuntimeError`). Help returns 0. Explicit callback exits follow
Typer's semantics: a `SystemExit` raised directly by a callback still propagates. The return value is
not a general exit-status API; use the default standalone mode at a process entry point.

**Example:**

```python
if __name__ == "__main__":
    app.run()
```

For embedding, call `app.run(["exec", "check"], standalone_mode=False)` after registering `check`.
Migration: callers that previously relied on `run()` swallowing `SystemExit` must now catch it
explicitly or choose non-standalone mode and handle exceptions.

### `BoostApp.run_all_workers()` and `BoostApp.stop()`

```python
run_all_workers() -> None
stop() -> None
```

`run_all_workers()` starts a thread for each registered worker and waits for a stop request or failure.
In the main thread it temporarily handles SIGINT and SIGTERM. `stop()` requests shutdown from any thread,
returns immediately, and is safe to repeat. Calls outside a run do not affect the next run.
Once stopping, the coordinator calls each live worker's `request_stop()` and joins all threads within
`shutdown_timeout`. It raises `TimeoutError` naming any remaining workers if there was no earlier failure.
Otherwise the timeout is logged and the earlier exception is re-raised. Their daemon threads may
continue; restarting is rejected while they remain alive. Concurrent calls are rejected too.

The first worker failure requests application shutdown and is re-raised with its original traceback
after cleanup. Later failures are logged without replacing it. A normal `run()` return before
application shutdown is a `RuntimeError`; finite workers must call `app.stop()` before returning or
use an individual command. A normal return or `asyncio.CancelledError` / `concurrent.futures.CancelledError`
during application shutdown is accepted. Cancellation before stop and all other exceptions (including
`SystemExit` / `KeyboardInterrupt`) propagate as failures. The same ordering preserves startup and
stop-request failures. The CLI converts a failure with a success `SystemExit` code as described above.
Aggregation of child exit codes by the external multi-process supervisor remains tracked in TB-009.

Workers must opt into managed stopping. `TemporalBoostWorker` supports this contract;
FastStream and ASGI adapter integration remains pending. See
[Graceful Shutdown](running_application.md#graceful-shutdown) for guarantees and limitations.

### `BoostApp.add_async_runtime()`

```python
add_async_runtime(worker_name: str, boost_worker: BaseBoostWorker) -> None
```

Register a custom worker's `run()` under a CLI command and include it in `run all`.
Set the worker's `name` to `worker_name` before registration.

### `BoostApp.get_registered_workers()`

Get list of all registered workers.

```python
get_registered_workers() -> list[BaseBoostWorker]
```

**Returns:**

- `list[BaseBoostWorker]`: List of registered workers.

## Worker Stop Contract

`BaseBoostWorker.request_stop() -> bool` is a non-blocking, thread-safe stop request.
Implementations must tolerate repeats and requests during startup. Return `True` when supported;
the default returns `False`. Async cleanup belongs on the resource-owning loop.

`AsyncBoostWorker` (exported from `temporal_boost` and `temporal_boost.workers`) provides this contract
for asyncio workers. Call `super().__init__()`, set `name`, implement async `run_async()` and `shutdown()`,
and inherit `run()` and `request_stop()`. The helper owns the loop, runs `shutdown()` once per run, and
waits for `run_async()` to return. `shutdown()` must handle partial startup and unblock `run_async()`.
If `run_async()` fails, its exception survives a subsequent cleanup failure, which is logged.
When `run_async()` is cancelled and cleanup fails, the cleanup error propagates so normal cancellation
cannot hide failed cleanup.
See the [example](advanced_usage.md#custom-worker-shutdown).

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
- `use_pydantic_data_converter` (bool | None): `True` enables Pydantic; `False` disables automatic
  Pydantic selection. `None` inherits the environment on initial configuration and leaves an existing
  builder unchanged. An explicit `data_converter` in `kwargs` takes priority.
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

Consume the worker's task queue. This never registers a CRON workflow, including when CRON parameters
are configured. `run <name>` uses this method; `run all` uses it for every registered worker.

```python
run() -> None
```

**Example:**

```python
worker.run()
```

### `TemporalBoostWorker.cron()`

Run the worker as a CRON worker.

Available as `cron <name>` only when both CRON parameters are configured. Calling this method directly
without them raises `RuntimeError` before creating a loop or connecting. It registers once per process
start, then keeps consuming the task queue until stopped.

Atomically starts or reuses the ID using `WorkflowIDConflictPolicy.USE_EXISTING`. Closed IDs are
rejected with `WorkflowAlreadyStartedError` using `WorkflowIDReusePolicy.REJECT_DUPLICATE`, subject
to server history retention. Reuse preserves the existing schedule and configuration. Local shutdown
does not cancel the server-side workflow. See [CRON identity](creating_application.md#cron-workflow-identity)
and the [UUID migration procedure](running_application.md#migrating-existing-uuid-cron-workflows).

```python
cron() -> None
```

**Example:**

```python
worker.cron()
```

Both commands own their event loop and use one lifecycle for startup, execution, and cleanup. A stop
during startup cancels pending connection work. CRON cleanup completes the local wait and cancels any
pending registration call, then stops the SDK worker. The adapter owns the SDK `run()` task and uses
its public `shutdown()` API; it does not also enter the SDK async context manager. Normal `run()` does
not register a CRON workflow. Local stop does not delete a server-side workflow.

Sequential runs are supported and rebuild the client, runtime, and SDK worker on the next loop.
Concurrent `run()` / `cron()` calls on the same adapter raise `RuntimeError`. Startup and execution
errors propagate after cleanup; later cleanup errors are logged without replacing the original error.
Unexpected cancellation now propagates too. SDK validation failure before starting does not wait on an
SDK `shutdown()` that could never finish. No public Client/Runtime close API exists in the supported
SDK: the adapter releases its and its builders' references, and does not close caller-supplied executors
or invent close methods. External references may keep SDK objects alive.

### `TemporalBoostWorker.request_stop()` and `TemporalBoostWorker.shutdown()`

```python
def request_stop() -> bool
async def shutdown() -> None
```

`request_stop()` returns `True` and requests stop without waiting, from any thread. Repeats are safe;
a request before the first run is remembered and prevents resource creation. Requests after stopping
have no effect on the next run. `shutdown()` before/after a run is a no-op. During a run it must be called
on the owning loop, requests stop, and waits for lifecycle completion, including any error. Concurrent
waiters share cleanup; cancelling a waiter does not cancel the lifecycle. A foreign-loop call raises
`RuntimeError` directing callers to `request_stop()`. Use `request_stop()` inside worker callbacks too.

SDK shutdown is invoked at most once for an active SDK run. After SDK `run()` has already completed,
its result is retrieved without another SDK shutdown call. On a shutdown failure the adapter cancels
and joins its SDK task before releasing references. A stuck SDK operation can still exceed its activity
grace period; `BoostApp.shutdown_timeout` bounds the coordinator's wait, not the SDK operation itself.

### Lifecycle states

The read-only `state` property reports:

| Value | Meaning |
| --- | --- |
| `created` | Constructed; no active lifecycle |
| `building` | Creating runtime, connecting client, and constructing the SDK worker |
| `running` | SDK run task started; CRON registration may still be pending |
| `stopping` | Cancelling startup/CRON work and waiting for SDK cleanup |
| `stopped` | Adapter and builder resource references released; another run is allowed |

Early stop or failure may skip `running`. Setup options should be configured before a run.

### Properties

- `temporal_client` (Client): Get Temporal client instance.
- `temporal_worker` (Worker): Get Temporal worker instance.
- `temporal_cron_runner` (MethodAsyncNoParam): Get CRON runner method.
- `cron_workflow_id` (str): Read-only resolved CRON workflow ID.
- `state`: Current lifecycle state. Client and SDK worker properties raise after cleanup until rebuilt.

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

The constructor's `use_pydantic_data_converter` flag inherits the environment when `None`, enables
Pydantic when `True`, and disables automatic selection when `False`. An explicit `data_converter`
in constructor kwargs or `set_kwargs()` takes priority over the flag.

### `TemporalClientBuilder.set_pydantic_data_converter()`

```python
def set_pydantic_data_converter(*, enabled: bool = True) -> None
```

Enable or disable automatic Pydantic selection for future builds. Calling without arguments enables it.
Passing `enabled=False` removes the automatic selection while preserving any explicit `data_converter`.

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
    graceful_shutdown_timeout: timedelta | None = None,
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

The builder passes `graceful_shutdown_timeout` directly to the SDK `Worker`. An explicit non-negative
`datetime.timedelta`, including zero, overrides the environment; omission or `None` uses
`config.GRACEFUL_SHUTDOWN_TIMEOUT` (30 seconds by default). A selected negative value raises `ValueError`
when constructing the builder. `BoostApp.add_worker()` and `TemporalBoostWorker` forward this option
through their worker kwargs without duplicating it.

This grace period begins when SDK shutdown is requested and controls how long activities may finish
before cancellation is requested. It does not cap total SDK shutdown time, initiate application stop,
or change application/process shutdown budgets. Workers omitting this option now receive the framework
default instead of the SDK's zero grace period.

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
- `GRACEFUL_SHUTDOWN_TIMEOUT`: SDK activity grace period (`timedelta`, default 30 seconds), independent of application shutdown budget
- `PROMETHEUS_BIND_ADDRESS`: Prometheus bind address
- `PROMETHEUS_COUNTERS_TOTAL_SUFFIX`: Counters total suffix flag
- `PROMETHEUS_UNIT_SUFFIX`: Unit suffix flag
- `PROMETHEUS_DURATIONS_AS_SECONDS`: Durations as seconds flag

For detailed configuration options, see [Configuration Guide](configuration.md).

