# Temporal-boost

![social_preview](https://socialify.git.ci/northpowered/temporal-boost/image?description=1&font=Source%20Code%20Pro&logo=https%3A%2F%2Fraw.githubusercontent.com%2Ftemporalio%2Fdocumentation%2Fmain%2Fstatic%2Fimg%2Ffavicon.svg&name=1&owner=1&pattern=Brick%20Wall&theme=Light)

[![Python 3.10+](https://img.shields.io/pypi/pyversions/temporal-boost.svg?style=for-the-badge)](https://pypi.org/project/temporal-boost)
[![PyPI](https://img.shields.io/pypi/v/temporal-boost.svg?style=for-the-badge)](https://pypi.org/project/temporal-boost)
[![MIT](https://img.shields.io/pypi/l/temporalio.svg?style=for-the-badge)](LICENSE)

Documentation is available on [GitHub Pages](https://northpowered.github.io/temporal-boost/)

Small framework based on [temporalio/sdk-python](https://github.com/temporalio/sdk-python) - create [Temporal](https://temporal.io/) microservices as fast as you can

## Requirements

- Python >= 3.10

## Features

- Create Temporal workers with FastAPI-style
- Add CRON workers with one code line
- Append ASGI (ex. FastAPI) workers like Temporal
- Auto documentation with web UI (like SwaggerUI in FastAPI)
- Build-in logger and OTLP tracer

## Installation

Install core:

```bash
pip install temporal-boost
# or
poetry add temporal-boost
```

Optional extras:

- faststream integration: `pip install "temporal-boost[faststream]"` or `poetry add temporal-boost -E faststream`
- uvicorn ASGI: `pip install "temporal-boost[uvicorn]"` or `poetry add temporal-boost -E uvicorn`
- hypercorn ASGI: `pip install "temporal-boost[hypercorn]"` or `poetry add temporal-boost -E hypercorn`
- granian ASGI: `pip install "temporal-boost[granian]"` or `poetry add temporal-boost -E granian`

## Quick start

```python
from temporal_boost import BoostApp
from temporalio import activity
from temporalio import workflow

# Create `BoostApp` object
app = BoostApp()


# Describe your activities/workflows
@activity.defn(name="test_boost_activity_1")
async def test_boost_activity_1(foo: str, bar: str) -> str:
    app.logger.info("This is built-in logger")
    return f"1_{foo}{bar}"


@activity.defn(name="test_boost_activity_2")
async def test_boost_activity_2(foo: str, bar: str) -> str:
    return f"2_{foo}{bar}"


@workflow.defn(name="TestCronWorkflow", sandboxed=False)
class TestCronWorkflow:
    @workflow.run
    async def run(self) -> None:
        app.logger.warning("With is cron workflow")
        return None


# Add async workers to your app (FastAPI style)

app.add_worker(
    "worker_1",
    "task_q_1",
    activities=[test_boost_activity_1],
    metrics_endpoint="0.0.0.0:9000"
)

app.add_worker(
    "worker_2",
    "task_q_2",
    activities=[test_boost_activity_2]
)

# Example of CRON worker
app.add_worker(
    "test_cron",
    "task_q_3",
    workflows=[TestCronWorkflow],
    cron_schedule="* * * * *",
    cron_runner=TestCronWorkflow.run
)

# Run your app and start workers with CLI
app.run()
```

```bash
python3 main.py

Usage: main.py [OPTIONS] COMMAND [ARGS]...

# Options:
#   --install-completion [bash|zsh|fish|powershell|pwsh]
#                                   Install completion for the specified shell.
#   --show-completion [bash|zsh|fish|powershell|pwsh]
#                                   Show completion for the specified shell, to
#                                   copy it or customize the installation.
#   --help                          Show this message and exit.

Commands:
  cron
  run

```

```bash
python3 main.py run

Usage: main.py run [OPTIONS] COMMAND [ARGS]...

# Options:
#   --help  Show this message and exit.

Commands:
  all
  test_cron
  worker_1
  worker_2
```

```bash
python3 main.py run worker_1

# 2023-09-20T21:25:12 | INFO     | Worker worker_1 was registered in CLI
# 2023-09-20T21:25:12 | INFO     | Worker worker_2 was registered in CLI
# 2023-09-20T21:25:12 | INFO     | Worker test_cron was registered in CLI
# 2023-09-20T21:25:12 | INFO     | Worker worker_1 started on task_q_1 queue

```

## Environment variables

Core configuration is managed via environment variables (see `temporal_boost/temporal/config.py`):

- `TEMPORAL_TARGET_HOST` (default: `localhost:7233`)
- `TEMPORAL_NAMESPACE` (default: `default`)
- `TEMPORAL_TLS` (default: `false`)
- `TEMPORAL_API_KEY` (optional)
- `TEMPORAL_IDENTITY` (optional)
- `TEMPORAL_USE_PYDANTIC_DATA_CONVERTER` (default: `false`)

Worker tuning:

- `TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS` (default: `300`)
- `TEMPORAL_MAX_CONCURRENT_ACTIVITIES` (default: `300`)
- `TEMPORAL_MAX_CONCURRENT_LOCAL_ACTIVITIES` (default: `100`)
- `TEMPORAL_MAX_WORKFLOW_TASK_POLLS` (default: `10`)
- `TEMPORAL_MAX_ACTIVITY_TASK_POLLS` (default: `10`)
- `TEMPORAL_NONSTICKY_TO_STICKY_RATIO` (default: `0.2`)
- `TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT` (seconds, default: `30`)

Telemetry (Prometheus runtime):

- `TEMPORAL_PROMETHEUS_BIND_ADDRESS` (e.g. `0.0.0.0:8801`)
- `TEMPORAL_PROMETHEUS_COUNTERS_TOTAL_SUFFIX` (default: `false`)
- `TEMPORAL_PROMETHEUS_UNIT_SUFFIX` (default: `false`)
- `TEMPORAL_PROMETHEUS_DURATIONS_AS_SECONDS` (default: `false`)

Example:

```bash
export TEMPORAL_TARGET_HOST=temporal.example.com:7233
export TEMPORAL_NAMESPACE=production
export TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
```
