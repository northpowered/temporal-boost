import os
from datetime import timedelta


def get_env_bool(name: str, *, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"true", "1", "yes"}


def get_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (ValueError, TypeError):
        return default


def get_env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (ValueError, TypeError):
        return default


# Client configuration
TARGET_HOST: str = os.getenv("TEMPORAL_TARGET_HOST", "localhost:7233")
CLIENT_NAMESPACE: str = os.getenv("TEMPORAL_NAMESPACE", "default")
CLIENT_TLS: bool = get_env_bool("TEMPORAL_TLS", default=False)
CLIENT_API_KEY: str | None = os.getenv("TEMPORAL_API_KEY", None)
CLIENT_IDENTITY: str | None = os.getenv("TEMPORAL_IDENTITY", None)
USE_PYDANTIC_DATA_CONVERTER: bool = get_env_bool("TEMPORAL_USE_PYDANTIC_DATA_CONVERTER", default=False)

# Worker configuration
MAX_CONCURRENT_WORKFLOW_TASKS: int = get_env_int("TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS", 300)
MAX_CONCURRENT_ACTIVITIES: int = get_env_int("TEMPORAL_MAX_CONCURRENT_ACTIVITIES", 300)
MAX_CONCURRENT_LOCAL_ACTIVITIES: int = get_env_int("TEMPORAL_MAX_CONCURRENT_LOCAL_ACTIVITIES", 100)
MAX_WORKFLOW_TASK_POLLS: int = get_env_int("TEMPORAL_MAX_WORKFLOW_TASK_POLLS", 10)
MAX_ACTIVITY_TASK_POLLS: int = get_env_int("TEMPORAL_MAX_ACTIVITY_TASK_POLLS", 10)
NONSTICKY_STICKY_RATIO: float = get_env_float("TEMPORAL_NONSTICKY_TO_STICKY_RATIO", default=0.2)
GRACEFUL_SHUTDOWN_TIMEOUT: timedelta = timedelta(seconds=get_env_int("TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT", 30))

# Prometheus configuration for Telemetry
PROMETHEUS_BIND_ADDRESS: str | None = os.getenv("TEMPORAL_PROMETHEUS_BIND_ADDRESS")
PROMETHEUS_COUNTERS_TOTAL_SUFFIX: bool = get_env_bool("TEMPORAL_PROMETHEUS_COUNTERS_TOTAL_SUFFIX", default=False)
PROMETHEUS_UNIT_SUFFIX: bool = get_env_bool("TEMPORAL_PROMETHEUS_UNIT_SUFFIX", default=False)
PROMETHEUS_DURATIONS_AS_SECONDS: bool = get_env_bool("TEMPORAL_PROMETHEUS_DURATIONS_AS_SECONDS", default=False)
