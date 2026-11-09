# Configuration

Temporal-boost uses environment variables for defaults and provides explicit application and worker
configuration. This guide covers the available options, their precedence, and when they are read.

## Table of Contents

- [Environment Loading](#environment-loading)
- [Temporal Client Configuration](#temporal-client-configuration)
- [Worker Configuration](#worker-configuration)
- [Prometheus Metrics Configuration](#prometheus-metrics-configuration)
- [Runtime Configuration](#runtime-configuration)
- [Configuration Priority](#configuration-priority)
- [Configuration Examples](#configuration-examples)

## Environment Loading

`temporal_boost.temporal.config` reads environment variables once, when the package is first imported.
Set the environment before importing `temporal_boost` or any module that imports it. Changing
`os.environ` afterward does not update these constants, even for a newly constructed app or builder.
To select different settings after import, pass explicit arguments or configure the worker before
initialization; see [when configuration becomes fixed](#when-configuration-becomes-fixed).

The package does not load `.env` files automatically. Load one before importing the package, or
prepare the process environment externally. See the [startup example](#using-configuration-files).
The installed `temporal-boost` command imports the package before importing your app module, so a
`.env` loader inside that module is too late for the CLI's configuration defaults. Prepare its
environment before starting the command.

## Temporal Client Configuration

These settings control how workers connect to the Temporal server.

### `TEMPORAL_TARGET_HOST`

**Type**: String  
**Default**: `localhost:7233`  
**Description**: Temporal server address (host:port)

```bash
export TEMPORAL_TARGET_HOST=temporal.example.com:7233
```

### `TEMPORAL_NAMESPACE`

**Type**: String  
**Default**: `default`  
**Description**: Temporal namespace to use

```bash
export TEMPORAL_NAMESPACE=production
```

### `TEMPORAL_TLS`

**Type**: Boolean  
**Default**: `false`  
**Description**: Enable TLS for Temporal connections

```bash
export TEMPORAL_TLS=true
```

Accepts: `true`, `1`, `yes` (case-insensitive)

### `TEMPORAL_API_KEY`

**Type**: String  
**Default**: `None`  
**Description**: API key for Temporal Cloud or secured clusters

```bash
export TEMPORAL_API_KEY=your-api-key-here
```

**Security Note**: Never commit API keys to version control. Use secrets management.

### `TEMPORAL_IDENTITY`

**Type**: String  
**Default**: `None`  
**Description**: Client identity for Temporal connections

```bash
export TEMPORAL_IDENTITY=worker-1
```

### `TEMPORAL_USE_PYDANTIC_DATA_CONVERTER`

**Type**: Boolean  
**Default**: `false`  
**Description**: Use Pydantic data converter for serialization

```bash
export TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
```

When enabled, Temporal-boost uses Pydantic models for data serialization, providing better type safety and validation.

`BoostApp(use_pydantic=...)` and `use_pydantic_data_converter` on `TemporalClientBuilder` or
`worker.configure_temporal_client()` use the same selection rule when creating a client builder:

| Argument | Behavior |
| --- | --- |
| `None` (default) | Inherit `TEMPORAL_USE_PYDANTIC_DATA_CONVERTER` |
| `True` | Enable the SDK Pydantic converter |
| `False` | Disable automatic Pydantic selection, even when the environment enables it |

An explicit `data_converter` passed to `TemporalClientBuilder`, `set_kwargs()`, or
`worker.configure_temporal_client()` takes priority over both the flag and environment setting.
Disabling the flag preserves that converter. Without an explicit converter, disabling the flag leaves
the Temporal SDK's default converter in use.

```python
app = BoostApp(use_pydantic=False)  # Overrides an environment value of true
worker = app.add_worker("example", "example-queue", activities=[my_activity])
worker.configure_temporal_client(data_converter=custom_converter)  # Explicit converter takes priority
```

Before client initialization, or after run cleanup, `configure_temporal_client()` updates the flag
only when given `True` or `False`; `None` leaves the previous selection unchanged. Late calls raise
`RuntimeError`; see [when configuration becomes fixed](#when-configuration-becomes-fixed). Use
`builder.set_pydantic_data_converter(enabled=False)` to disable Pydantic on a standalone builder;
`builder.set_pydantic_data_converter()` still enables it. Each subsequent `build()` uses the current
selection without retaining a converter automatically added by an earlier build. These changes apply
to future client builds; they do not reconfigure an already connected client.

**Migration:** Code that relied on `False` enabling Pydantic must pass `True`. Code that supplied both
an explicit converter and an enabled Pydantic flag now uses the explicit converter; remove it to use
the SDK Pydantic converter.

## Worker Configuration

These settings control worker behavior and resource limits.

The six concurrency, poll-count, and polling-ratio options below use the environment/default only
when the corresponding worker argument is omitted or `None`. Selected values are validated when
`TemporalWorkerBuilder` is constructed, including through `BoostApp.add_worker()`:

| Worker argument | Accepted values |
| --- | --- |
| `max_concurrent_workflow_tasks` | Positive integer |
| `max_concurrent_activities` | Positive integer |
| `max_concurrent_local_activities` | Positive integer |
| `max_concurrent_workflow_task_polls` | Positive integer |
| `max_concurrent_activity_task_polls` | Positive integer |
| `nonsticky_to_sticky_poll_ratio` | Finite, non-negative `int` or `float`, including `0.0`; no upper cap |

Wrong types, including booleans and numeric strings, raise `TypeError`; out-of-range values raise
`ValueError`. Counts reject floats, including `1.0`. Explicit values do not silently fall back:
replace an old zero count with `None` or omit it to select configuration. A selected zero or negative
count from the environment also raises `ValueError`. A valid explicit argument can override an
invalid configured default. Environment parsing still occurs at import time; malformed integer/float
text retains the existing parser fallback to the framework default.

The SDK enforces additional constraints during `build()`, including workflow task concurrency and
workflow poll counts of at least two when workflow caching is enabled (`max_cached_workflows > 0`).
With caching disabled, one is valid. The builder's non-negative, finite ratio check rejects unusable
settings that SDK Core itself does not range-check; it does not impose a `1.0` upper limit.

```python
app.add_worker("worker", "queue", workflows=[MyWorkflow], nonsticky_to_sticky_poll_ratio=0.0)
```

The zero ratio reaches the SDK unchanged. The SDK still uses at least one poller per sticky/non-sticky
queue when caching is enabled; zero does not disable non-sticky polling.

### `TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS`

**Type**: Integer  
**Default**: `300`  
**Description**: Maximum concurrent workflow tasks per worker

```bash
export TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=500
```

Increase for high workflow throughput, decrease to limit resource usage.

### `TEMPORAL_MAX_CONCURRENT_ACTIVITIES`

**Type**: Integer  
**Default**: `300`  
**Description**: Maximum concurrent activity executions per worker

```bash
export TEMPORAL_MAX_CONCURRENT_ACTIVITIES=200
```

Tune based on your activity workload and available resources.

### `TEMPORAL_MAX_CONCURRENT_LOCAL_ACTIVITIES`

**Type**: Integer  
**Default**: `100`  
**Description**: Maximum concurrent local activity executions

```bash
export TEMPORAL_MAX_CONCURRENT_LOCAL_ACTIVITIES=50
```

Local activities execute in the same process as workflows.

### `TEMPORAL_MAX_WORKFLOW_TASK_POLLS`

**Type**: Integer  
**Default**: `10`  
**Description**: Maximum concurrent workflow task polls

```bash
export TEMPORAL_MAX_WORKFLOW_TASK_POLLS=20
```

Controls how many workflow tasks can be polled simultaneously.

### `TEMPORAL_MAX_ACTIVITY_TASK_POLLS`

**Type**: Integer  
**Default**: `10`  
**Description**: Maximum concurrent activity task polls

```bash
export TEMPORAL_MAX_ACTIVITY_TASK_POLLS=20
```

Controls how many activity tasks can be polled simultaneously.

### `TEMPORAL_NONSTICKY_TO_STICKY_RATIO`

**Type**: Float  
**Default**: `0.2`  
**Description**: Ratio of non-sticky to sticky workflow task polls

```bash
export TEMPORAL_NONSTICKY_TO_STICKY_RATIO=0.3
```

Sticky workflows improve performance by keeping workflow state in memory.

### `TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT`

**Type**: Integer (seconds)  
**Default**: `30`  
**Description**: Activity grace period passed to the Temporal SDK worker as `graceful_shutdown_timeout`

```bash
export TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT=60
```

When SDK worker shutdown begins, activities get this grace period to finish before the SDK requests
cancellation. Zero requests cancellation without a grace period. SDK shutdown still waits for activities
to finish; an activity that ignores cancellation can keep shutdown waiting beyond this duration.

Override the environment per worker with a `datetime.timedelta`:

```python
from datetime import timedelta

worker = app.add_worker(
    "payments",
    "payments_queue",
    activities=[process_payment],
    graceful_shutdown_timeout=timedelta(seconds=45),
)
```

An explicit value, including `timedelta(0)`, takes priority. Omission or `None` uses the environment
constant, read when configuration is imported; the fallback is 30 seconds. Invalid integer text uses
the same fallback. A selected negative duration raises `ValueError` when the worker builder is created.
An explicit non-negative value can override a negative environment value.

**Behavior change:** workers omitting this option now receive the framework's environment/default
grace period (30 seconds by default). Previously this setting was ignored and the SDK defaulted to
zero unless a value was passed explicitly through worker kwargs.

The application coordinator has a separate budget, `BoostApp(shutdown_timeout=30.0)`, for joining all
worker threads. The external launcher's `--shutdown-timeout` (default 30 seconds) sets a separate shared
child-process grace period, followed by up to 5 seconds after terminate and 5 seconds after kill.
Give the outer process budget enough time for the inner coordinator and SDK cleanup. This setting changes
neither budget and does not initiate shutdown. The Temporal adapter participates in managed stopping through
`request_stop()`; its SDK cleanup still depends on activities respecting cancellation.
See [Graceful Shutdown](running_application.md#graceful-shutdown) for current guarantees and limitations.

## Prometheus Metrics Configuration

These settings control Prometheus metrics collection and export.

### `TEMPORAL_PROMETHEUS_BIND_ADDRESS`

**Type**: String  
**Default**: `None`  
**Description**: Bind address for Prometheus metrics endpoint

```bash
export TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
```

When set, each Temporal worker runtime exposes `/metrics` at this address. Concurrent runtimes need
distinct endpoints; a bind conflict fails startup instead of disabling telemetry. Override the address
per worker with `configure_temporal_runtime()`, and allocate separate ports or network addresses for
each process. `--workers N` does not assign metrics ports. Scrape every endpoint; see
[Metrics Across Workers and Processes](advanced_usage.md#metrics-across-workers-and-processes).

The SDK exporter does not use `PROMETHEUS_MULTIPROC_DIR`; that directory does not aggregate SDK metrics.

### `TEMPORAL_PROMETHEUS_COUNTERS_TOTAL_SUFFIX`

**Type**: Boolean  
**Default**: `false`  
**Description**: Append `_total` suffix to counter metrics

```bash
export TEMPORAL_PROMETHEUS_COUNTERS_TOTAL_SUFFIX=true
```

### `TEMPORAL_PROMETHEUS_UNIT_SUFFIX`

**Type**: Boolean  
**Default**: `false`  
**Description**: Append unit suffix to metric names

```bash
export TEMPORAL_PROMETHEUS_UNIT_SUFFIX=true
```

### `TEMPORAL_PROMETHEUS_DURATIONS_AS_SECONDS`

**Type**: Boolean  
**Default**: `false`  
**Description**: Express durations in seconds instead of milliseconds

```bash
export TEMPORAL_PROMETHEUS_DURATIONS_AS_SECONDS=true
```

## Runtime Configuration

Runtime configuration is done programmatically. See [Advanced Usage](advanced_usage.md) for details.

The defaults for `prometheus_bind_address`, `prometheus_counters_total_suffix`,
`prometheus_unit_suffix`, and `prometheus_durations_as_seconds` are captured when
`TemporalRuntimeBuilder.__init__()` and `worker.configure_temporal_runtime()` are defined during
import. Changing `os.environ` or even assigning new values to `config.PROMETHEUS_*` afterward does
not change omitted arguments. Supply explicit runtime arguments to change them before runtime creation.

Each `configure_temporal_runtime()` call replaces the runtime configuration; omitted fields return
to their function defaults. An explicit `metrics` backend takes priority over the bind address.
With `metrics=None`, passing `prometheus_bind_address=None` disables the implicit Prometheus exporter,
even if the imported environment supplied an address. Explicit `False` or `None` for a Prometheus
suffix/duration flag produces `False`; `None` does not re-read the environment.

## When Configuration Becomes Fixed

Configure a Temporal worker before starting it. Settings become fixed at these points:

| Worker condition | Runtime configuration | Client configuration |
| --- | --- | --- |
| Created, no resources initialized | Allowed | Allowed |
| Runtime created through `temporal_client_runtime`, client not initialized | Raises `RuntimeError` | Allowed |
| Client/SDK worker initialization started or completed | Raises `RuntimeError` | Raises `RuntimeError` |
| Lifecycle is `building`, `running`, or `stopping` | Raises `RuntimeError` | Raises `RuntimeError` |
| Run cleanup completed (`stopped`), resources released | Allowed for the next run | Allowed for the next run |

The `temporal_client_runtime` property creates and caches a runtime when first read, even before a
run. This can bind a Prometheus port. Set runtime options before reading it. Repeated reads return the
same object; reconfiguration is rejected without changing its builder. The `created` lifecycle state
means no run is active, so it can still contain a runtime initialized through this property.

Rejected client calls also leave both builders and SDK objects unchanged. There is no automatic
reconnect, runtime replacement, or live update of an SDK worker. After a run or startup failure has
completed cleanup, both configuration methods are available again. The next run builds fresh objects
using those settings. Reading `temporal_client_runtime` after cleanup creates a new runtime and fixes
its options again. A failed runtime constructor that leaves no cached runtime can be reconfigured
before retrying, provided no lifecycle is active.

```python
worker = app.add_worker("consumer", "queue", activities=[my_activity])
worker.configure_temporal_runtime(prometheus_bind_address="127.0.0.1:9101")
worker.configure_temporal_client(namespace="production")
# Optional inspection now creates the runtime and fixes its telemetry options:
runtime = worker.temporal_client_runtime
```

**Migration:** Move configuration calls before `run()`/`cron()` and before the first runtime property
read. For a later change, request stop, wait for the run to return and cleanup to complete, then
configure the next run. To discard an initialized preview runtime without running the adapter, create
a new worker instead of replacing its runtime. External references may keep the old runtime/exporter
alive, so release them before reusing its port.

SDK worker options such as activities, interceptors, and concurrency are supplied when constructing
the adapter or calling `app.add_worker()`; use a new adapter to change those options. Standalone
`TemporalClientBuilder`/`TemporalWorkerBuilder` instances remain mutable: their setters affect future
builds and do not alter objects already returned by `build()`.

## Configuration Priority

Endpoint and namespace are selected independently in this order (highest to lowest priority):

1. **Explicit worker configuration**: the last non-`None` `target_host` or `namespace` supplied to
   `configure_temporal_client()` before client initialization.
2. **BoostApp initialization parameters**: `temporal_endpoint` and `temporal_namespace`.
3. **Imported environment values**: `TEMPORAL_TARGET_HOST` and `TEMPORAL_NAMESPACE`.
4. **Built-in defaults**: `localhost:7233` and `default`.

When an existing worker's client builder is configured again, omitted fields and `None` leave its
previous values unchanged. Setting only the namespace preserves the selected endpoint. A standalone
`TemporalClientBuilder` has no app layer: constructor arguments override the imported configuration,
and subsequent setters override its stored values for future builds.

```bash
export TEMPORAL_TARGET_HOST=temporal.prod:7233
export TEMPORAL_NAMESPACE=production
```

```python
from temporal_boost import BoostApp

# The app endpoint wins over the environment; namespace still comes from the environment.
app = BoostApp(temporal_endpoint="temporal.dev:7233")
worker = app.add_worker("consumer", "queue", activities=[my_activity])
# This worker connects to temporal.dev:7233 in the isolated namespace.
worker.configure_temporal_client(namespace="isolated")
worker.configure_temporal_client(target_host=None)  # Keeps temporal.dev:7233
```

Other fields have their own selection rules:

| Fields | Selection rule |
| --- | --- |
| Client string constructor arguments (`target_host`, `namespace`, `api_key`, `identity`) | `None` or an empty string falls back to imported config. Worker configuration and app endpoint/namespace updates use setters, which preserve an explicit empty string. Empty strings do not reset configuration and may be rejected by the SDK. |
| `tls` | `None` on initial client configuration inherits imported config; explicit `False` overrides `True`. On an existing worker builder, `None` leaves the setting unchanged. |
| Pydantic flag / `data_converter` | Explicit converter wins over the flag; the flag distinguishes `None`, `False`, and `True`. See [converter selection](#temporal_use_pydantic_data_converter). |
| Worker counts, ratio, and activity grace period | Only `None` selects imported config. Zero is valid for ratio and grace period; counts must be positive. See [worker configuration](#worker-configuration). |
| Prometheus defaults | Omitted arguments use defaults captured during import; explicit arguments follow the [runtime rules](#runtime-configuration). |

## Configuration Examples

### Development Configuration

```bash
# .env.development
TEMPORAL_TARGET_HOST=localhost:7233
TEMPORAL_NAMESPACE=development
TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
TEMPORAL_MAX_CONCURRENT_ACTIVITIES=10
TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=10
```

### Production Configuration

```bash
# .env.production
TEMPORAL_TARGET_HOST=temporal.production.example.com:7233
TEMPORAL_NAMESPACE=production
TEMPORAL_TLS=true
TEMPORAL_API_KEY=${TEMPORAL_API_KEY}  # From secrets manager
TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
TEMPORAL_MAX_CONCURRENT_ACTIVITIES=300
TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=300
TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT=60
```

### High-Performance Configuration

```bash
# .env.high-performance
TEMPORAL_TARGET_HOST=temporal.cluster.example.com:7233
TEMPORAL_NAMESPACE=production
TEMPORAL_TLS=true
TEMPORAL_MAX_CONCURRENT_ACTIVITIES=1000
TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=500
TEMPORAL_MAX_WORKFLOW_TASK_POLLS=50
TEMPORAL_MAX_ACTIVITY_TASK_POLLS=50
TEMPORAL_NONSTICKY_TO_STICKY_RATIO=0.1
TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
```

### Resource-Limited Configuration

```bash
# .env.limited-resources
TEMPORAL_TARGET_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_MAX_CONCURRENT_ACTIVITIES=50
TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=50
TEMPORAL_MAX_CONCURRENT_LOCAL_ACTIVITIES=20
TEMPORAL_MAX_WORKFLOW_TASK_POLLS=5
TEMPORAL_MAX_ACTIVITY_TASK_POLLS=5
```

### Using Configuration Files

For direct script execution, install `python-dotenv` separately and load the file before any import
of the package or your worker modules:

```python
from dotenv import load_dotenv

load_dotenv(".env")  # Must run before importing temporal_boost

from temporal_boost import BoostApp

app = BoostApp()
```

By default, `load_dotenv()` preserves variables already present in the process environment. This
controls how the environment is prepared; the explicit app/worker precedence above still applies.

### Configuration Validation

Validate configuration at startup:

```python
import os
from temporal_boost import BoostApp

def validate_config():
    """Validate required configuration."""
    required_vars = [
        "TEMPORAL_TARGET_HOST",
        "TEMPORAL_NAMESPACE",
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ValueError(f"Missing required environment variables: {missing}")

validate_config()
app = BoostApp()
```

### Startup Environment and Explicit Overrides

Prepare environment defaults before the first package import in a fresh process:

```python
import os

# Set defaults before importing temporal_boost or your application modules.
os.environ["TEMPORAL_TARGET_HOST"] = "localhost:7233"
os.environ["TEMPORAL_NAMESPACE"] = "test"

from temporal_boost import BoostApp

app = BoostApp()
```

If the package has already been imported, use explicit settings for a new app or a worker whose
client has not been initialized:

```python
from temporal_boost import BoostApp

app = BoostApp(temporal_endpoint="localhost:7233", temporal_namespace="test")
worker = app.add_worker("consumer", "queue", activities=[my_activity])
worker.configure_temporal_client(namespace="another-test")
```

These calls configure future resource creation. They do not update an active client or runtime.

### Configuration Tips

1. **Use environment-specific files**: `.env.development`, `.env.production`
2. **Never commit secrets**: Use secrets management for API keys
3. **Document defaults**: Make configuration defaults clear in documentation
4. **Validate early**: Check configuration at application startup
5. **Use types**: Convert string environment variables to appropriate types
6. **Monitor configuration**: Log configuration values (without secrets) at startup

### Common Configuration Patterns

#### Pattern 1: Environment-Based

Run this bootstrap before importing `temporal_boost` or your application modules:

```python
import os

env = os.getenv("ENVIRONMENT", "development")
if env == "production":
    os.environ.setdefault("TEMPORAL_TLS", "true")
    os.environ.setdefault("TEMPORAL_PROMETHEUS_BIND_ADDRESS", "0.0.0.0:9090")

from temporal_boost import BoostApp

app = BoostApp()
```

#### Pattern 2: Configuration Class

An application-owned settings class reads the environment independently. Pass its values explicitly
to `BoostApp` or worker configuration; creating the settings object does not update package constants.

```python
from dataclasses import dataclass
import os

@dataclass
class TemporalConfig:
    host: str
    namespace: str
    tls: bool
    api_key: str | None = None
    
    @classmethod
    def from_env(cls):
        return cls(
            host=os.getenv("TEMPORAL_TARGET_HOST", "localhost:7233"),
            namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
            tls=os.getenv("TEMPORAL_TLS", "false").lower() == "true",
            api_key=os.getenv("TEMPORAL_API_KEY"),
        )

config = TemporalConfig.from_env()
```

#### Pattern 3: Pydantic Settings

```python
from pydantic import BaseSettings

class TemporalSettings(BaseSettings):
    temporal_target_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_tls: bool = False
    temporal_api_key: str | None = None
    
    class Config:
        env_prefix = "TEMPORAL_"
        case_sensitive = False

settings = TemporalSettings()
```

### Security Best Practices

1. **Never log secrets**: Filter out API keys from logs
2. **Use secrets management**: AWS Secrets Manager, HashiCorp Vault, etc.
3. **Rotate credentials**: Regularly rotate API keys
4. **Use TLS in production**: Always enable TLS for production
5. **Restrict access**: Use network policies to restrict Temporal access
6. **Audit configuration**: Log configuration changes in production

### Troubleshooting Configuration

#### Check Current Configuration

```python
import os
from temporal_boost.temporal import config

print(f"Host: {config.TARGET_HOST}")
print(f"Namespace: {config.CLIENT_NAMESPACE}")
print(f"TLS: {config.CLIENT_TLS}")
print(f"Max Activities: {config.MAX_CONCURRENT_ACTIVITIES}")
```

#### Validate Configuration

```python
from temporal_boost.temporal import config

def validate():
    assert config.TARGET_HOST, "TEMPORAL_TARGET_HOST not set"
    assert config.CLIENT_NAMESPACE, "TEMPORAL_NAMESPACE not set"
    if config.CLIENT_TLS and not config.CLIENT_API_KEY:
        print("Warning: TLS enabled but no API key provided")

validate()
```

