# Creating application

## Base code example

This is the base code snippet to start working with the framework. Create a `BoostApp` object, set configuration via environment variables, and run it.

```python
import logging
from datetime import timedelta
from temporalio import activity, workflow
from temporal_boost import BoostApp

logging.basicConfig(level=logging.INFO)

app = BoostApp(
    name="BoostApp example",
    temporal_endpoint="localhost:7233",
    temporal_namespace="default",
    use_pydantic=True,
)

@activity.defn(name="my_activity")
async def my_activity(name: str) -> str:
    return f"Hello, {name}!"

@workflow.defn(sandboxed=False, name="MyWorkflow")
class MyWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            my_activity,
            name,
            task_queue="my_queue_1",
            start_to_close_timeout=timedelta(minutes=1),
        )

app.add_worker(
    "worker_1",
    "my_queue_1",
    activities=[my_activity],
)
app.add_worker(
    "worker_2",
    "my_queue_2",
    workflows=[MyWorkflow],
)

if __name__ == "__main__":
    app.run()
```

## Configuration via environment variables

All configuration is now handled via environment variables. You can set the following variables (see `temporal_boost/temporal/config.py` for the full list):

- `TEMPORAL_TARGET_HOST` (default: `localhost:7233`)
- `TEMPORAL_NAMESPACE` (default: `default`)
- `TEMPORAL_TLS` (default: `false`)
- `TEMPORAL_API_KEY` (optional)
- `TEMPORAL_IDENTITY` (optional)
- `TEMPORAL_USE_PYDANTIC_DATA_CONVERTER` (default: `false`)
- Worker concurrency, Prometheus metrics, and more (see config.py)

Example:

```bash
export TEMPORAL_TARGET_HOST=temporal.example.com:7233
export TEMPORAL_NAMESPACE=production
export TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
```

## Adding Temporal workers

To add a worker to the app, use the `add_worker` method:

```python
def add_worker(
    self,
    worker_name: str,
    task_queue: str,
    workflows: list = [],
    activities: list = [],
    cron_schedule: str | None = None,
    cron_runner: typing.Coroutine | None = None,
) -> None:
```

- `worker_name`: Unique name for the worker (do not use reserved names like `all` or `internal`).
- `task_queue`: Task queue for activities and workflows.
- `workflows`: List of workflow classes.
- `activities`: List of activity functions.
- `cron_schedule`: (Optional) CRON string for scheduled workflows.
- `cron_runner`: (Optional) Workflow run method for CRON workers.

### Examples

```python
app.add_worker(
    "worker_1",
    "my_queue_1",
    activities=[my_activity],
)
app.add_worker(
    "worker_2",
    "my_queue_2",
    workflows=[MyWorkflow],
)
app.add_worker(
    "worker_3",
    "my_queue_3",
    workflows=[MyWorkflow2],
    activities=[my_activity2],
)
```

## Adding CRON workers

To execute a workflow on a schedule, create a CRON worker:

```python
app.add_worker(
    "worker_4",
    "task_q_4",
    workflows=[MyWorkflow],
    cron_runner=MyWorkflow.run,
    cron_schedule="* * * * *"
)
```

- `cron_runner` is a coroutine (usually the workflow's `run` method) that will be started according to the `cron_schedule`.

## Adding ASGI workers

To add a FastAPI (or any ASGI) application as a worker:

```python
from fastapi import FastAPI
fastapi_app = FastAPI(docs_url="/doc")

app.add_asgi_worker("asgi_worker", fastapi_app, "0.0.0.0", 8000)
```

You can specify the ASGI worker type ("uvicorn", "hypercorn", "granian") or use auto-detection:

```python
app.add_asgi_worker("asgi_worker", fastapi_app, "0.0.0.0", 8000, worker_type="auto")
```

The application will be run with the selected ASGI server in the appropriate async runtime.
