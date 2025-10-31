# Configuration

Temporal-boost uses environment variables for configuration, providing a flexible and 12-factor app compliant approach. This guide covers all available configuration options.

## Table of Contents

- [Temporal Client Configuration](#temporal-client-configuration)
- [Worker Configuration](#worker-configuration)
- [Prometheus Metrics Configuration](#prometheus-metrics-configuration)
- [Runtime Configuration](#runtime-configuration)
- [Configuration Priority](#configuration-priority)
- [Configuration Examples](#configuration-examples)

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

## Worker Configuration

These settings control worker behavior and resource limits.

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
**Description**: Timeout for graceful shutdown

```bash
export TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT=60
```

Workers will wait this long for running activities to complete before shutting down.

## Prometheus Metrics Configuration

These settings control Prometheus metrics collection and export.

### `TEMPORAL_PROMETHEUS_BIND_ADDRESS`

**Type**: String  
**Default**: `None`  
**Description**: Bind address for Prometheus metrics endpoint

```bash
export TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
```

When set, exposes Prometheus metrics at `/metrics` endpoint.

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

## Configuration Priority

Configuration is loaded in this order (highest to lowest priority):

1. **Environment variables** - Highest priority
2. **BoostApp initialization parameters**
3. **Default values** - Lowest priority

Example:

```python
# Environment variable: TEMPORAL_TARGET_HOST=temporal.prod:7233
# BoostApp parameter: temporal_endpoint="temporal.dev:7233"
# Result: Uses "temporal.prod:7233" (environment variable wins)
app = BoostApp(temporal_endpoint="temporal.dev:7233")
```

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

Load from `.env` file:

```python
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Access configuration
host = os.getenv("TEMPORAL_TARGET_HOST", "localhost:7233")
```

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

### Dynamic Configuration

Override configuration programmatically:

```python
import os

# Override for testing
os.environ["TEMPORAL_TARGET_HOST"] = "localhost:7233"
os.environ["TEMPORAL_NAMESPACE"] = "test"

app = BoostApp()
```

### Configuration Tips

1. **Use environment-specific files**: `.env.development`, `.env.production`
2. **Never commit secrets**: Use secrets management for API keys
3. **Document defaults**: Make configuration defaults clear in documentation
4. **Validate early**: Check configuration at application startup
5. **Use types**: Convert string environment variables to appropriate types
6. **Monitor configuration**: Log configuration values (without secrets) at startup

### Common Configuration Patterns

#### Pattern 1: Environment-Based

```python
import os

env = os.getenv("ENVIRONMENT", "development")
if env == "production":
    os.environ.setdefault("TEMPORAL_TLS", "true")
    os.environ.setdefault("TEMPORAL_PROMETHEUS_BIND_ADDRESS", "0.0.0.0:9090")
```

#### Pattern 2: Configuration Class

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

