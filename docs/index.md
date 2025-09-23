# Getting started

![](https://socialify.git.ci/northpowered/temporal-boost/image?description=1&font=Source%20Code%20Pro&logo=https%3A%2F%2Fraw.githubusercontent.com%2Ftemporalio%2Fdocumentation%2Fmain%2Fstatic%2Fimg%2Ffavicon.svg&name=1&owner=1&pattern=Brick%20Wall&theme=Light)

## About the framework

Temporal-boost is a lightweight framework for fast and comfortable development of Temporal-based microservices. It is based on the standard Temporal SDK for Python, but offers a FastAPI-inspired code organization and modern developer experience.

### Main dependencies

- [x] [Temporal SDK (python)](https://github.com/temporalio/sdk-python)
- [x] [Pydantic - for serialization](https://github.com/pydantic/pydantic)
- [x] [Typer - for CLI interface](https://github.com/fastapi/typer)
- [x] [Python logging - built-in logging configuration]
- [x] [Hypercorn, Uvicorn, Granian - for running ASGI applications](https://github.com/pgjones/hypercorn)

### Main features

- [x] FastAPI-style application with pluggable workers (like routers)
- [x] Centralized logging and tracing management
- [x] Simple CRON workflow support
- [x] Easy integration of external ASGI applications (FastAPI, etc.)
- [x] Flexible configuration via environment variables

## Installation

```bash
poetry add temporal-boost
```

or

```bash
pip install temporal-boost
```

## Quick start

### Code example
>
> main.py

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

# Example: add ASGI worker (FastAPI, etc.)
# from fastapi import FastAPI
# fastapi_app = FastAPI()
# app.add_asgi_worker("asgi_worker", fastapi_app, "0.0.0.0", 8000)

if __name__ == "__main__":
    app.run()
```

### Configuration

All configuration (Temporal endpoint, namespace, TLS, metrics, etc.) is handled via environment variables. See `temporal_boost/temporal/config.py` for available options.

### Start example application

Starting all workers at once:

```bash
python3 main.py run all
```

You can also run a specific worker by name (see advanced usage in docs).
