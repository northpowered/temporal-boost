# Getting started

![](https://socialify.git.ci/northpowered/temporal-boost/image?description=1&font=Source%20Code%20Pro&logo=https%3A%2F%2Fraw.githubusercontent.com%2Ftemporalio%2Fdocumentation%2Fmain%2Fstatic%2Fimg%2Ffavicon.svg&name=1&owner=1&pattern=Brick%20Wall&theme=Light)

## About the framework

**Temporal-boost** is a lightweight, high-level framework for rapid development of Temporal-based microservices in Python. Built on top of the official [Temporal Python SDK](https://github.com/temporalio/sdk-python), it provides a FastAPI-inspired developer experience that makes building Temporal applications faster and more intuitive.

If you're familiar with FastAPI's declarative style and want to build reliable, scalable workflows with Temporal, this framework is designed for you.

### Why Temporal-boost?

- **FastAPI-style API**: Organize your Temporal workers similar to how you organize FastAPI routes
- **Zero boilerplate**: Focus on your business logic, not infrastructure setup
- **Production-ready**: Built-in logging, tracing, metrics, and graceful shutdown
- **Flexible**: Support for activities, workflows, CRON schedules, and ASGI apps
- **Type-safe**: Full type hints and Pydantic integration support

### Main dependencies

- [**Temporal SDK (Python)**](https://github.com/temporalio/sdk-python) - Core Temporal functionality
- [**Pydantic**](https://github.com/pydantic/pydantic) - Data validation and serialization
- [**Typer**](https://github.com/fastapi/typer) - Modern CLI interface
- **Python logging** - Built-in structured logging configuration
- **ASGI servers** - Hypercorn, Uvicorn, Granian for running web applications

### Main features

- ✅ **FastAPI-style application** with pluggable workers (like routers)
- ✅ **Centralized logging and tracing** management
- ✅ **Simple CRON workflow** support with declarative scheduling
- ✅ **ASGI integration** for FastAPI, Starlette, or any ASGI application
- ✅ **FastStream integration** for event-driven architectures
- ✅ **Environment-based configuration** for all settings
- ✅ **Prometheus metrics** support out of the box
- ✅ **Graceful shutdown** handling
- ✅ **CLI interface** for running workers individually or together

## Installation

### Basic installation

Install the core package:

```bash
pip install temporal-boost
```

or with Poetry:

```bash
poetry add temporal-boost
```

### Optional extras

Install additional features as needed:

```bash
# FastStream integration for event-driven workers
pip install "temporal-boost[faststream]"

# ASGI server support (choose one or more)
pip install "temporal-boost[uvicorn]"      # Uvicorn ASGI server
pip install "temporal-boost[hypercorn]"    # Hypercorn ASGI server
pip install "temporal-boost[granian]"      # Granian ASGI server

# Install all extras
pip install "temporal-boost[faststream,uvicorn,hypercorn,granian]"
```

### Requirements

- Python >= 3.10
- Access to a Temporal server (local or remote)

## Quick start

### Your first Temporal-boost application

Create a file `main.py`:

```python
import logging
from datetime import timedelta
from temporalio import activity, workflow
from temporal_boost import BoostApp

logging.basicConfig(level=logging.INFO)

# Create your BoostApp instance
app = BoostApp(name="my-first-app")

# Define an activity
@activity.defn(name="greet_activity")
async def greet_activity(name: str) -> str:
    return f"Hello, {name}!"

# Define a workflow
@workflow.defn(sandboxed=False, name="GreetingWorkflow")
class GreetingWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            greet_activity,
            name,
            task_queue="greeting_queue",
            start_to_close_timeout=timedelta(minutes=1),
        )

# Register workers
app.add_worker(
    "greeting_worker",
    "greeting_queue",
    activities=[greet_activity],
    workflows=[GreetingWorkflow],
)

if __name__ == "__main__":
    app.run()
```

### Configuration

Set environment variables (or use defaults):

```bash
export TEMPORAL_TARGET_HOST=localhost:7233
export TEMPORAL_NAMESPACE=default
```

See the [Configuration Guide](configuration.md) for all available options.

### Running your application

Start all workers:

```bash
python3 main.py run all
```

Or run a specific worker:

```bash
python3 main.py run greeting_worker
```

### What's next?

- 📖 [Creating Applications](creating_application.md) - Learn how to structure your application
- 🚀 [Running Applications](running_application.md) - Deployment and production tips
- 🔧 [Configuration Guide](configuration.md) - Complete configuration reference
- 💡 [Examples](examples.md) - Comprehensive examples and patterns
- 🎯 [Advanced Usage](advanced_usage.md) - Customization and advanced features

### Example: Execute a workflow

Create a client script to start your workflow:

```python
import asyncio
from temporalio.client import Client

async def main():
    client = await Client.connect("localhost:7233")
    
    result = await client.execute_workflow(
        "GreetingWorkflow",
        "World",
        id="greeting-workflow-1",
        task_queue="greeting_queue",
    )
    
    print(f"Workflow result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:

```bash
python3 client.py
# Output: Workflow result: Hello, World!
```
