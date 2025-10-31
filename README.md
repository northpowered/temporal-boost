# Temporal-boost

![social_preview](https://socialify.git.ci/northpowered/temporal-boost/image?description=1&font=Source%20Code%20Pro&logo=https%3A%2F%2Fraw.githubusercontent.com%2Ftemporalio%2Fdocumentation%2Fmain%2Fstatic%2Fimg%2Ffavicon.svg&name=1&owner=1&pattern=Brick%20Wall&theme=Light)

[![Python 3.10+](https://img.shields.io/pypi/pyversions/temporal-boost.svg?style=for-the-badge)](https://pypi.org/project/temporal-boost)
[![PyPI](https://img.shields.io/pypi/v/temporal-boost.svg?style=for-the-badge)](https://pypi.org/project/temporal-boost)
[![MIT](https://img.shields.io/pypi/l/temporalio.svg?style=for-the-badge)](LICENSE)

**Temporal-boost** is a lightweight, high-level framework for rapid development of Temporal-based microservices in Python. Built on top of the official [Temporal Python SDK](https://github.com/temporalio/sdk-python), it provides a FastAPI-inspired developer experience.

📖 **[Full Documentation](https://northpowered.github.io/temporal-boost/)** | 🐛 [Issues](https://github.com/northpowered/temporal-boost/issues) | 💬 [Discussions](https://github.com/northpowered/temporal-boost/discussions)

## Features

- ✅ **FastAPI-style API** - Organize workers like FastAPI routes
- ✅ **Zero boilerplate** - Focus on business logic, not infrastructure
- ✅ **CRON workers** - Scheduled workflows with one line of code
- ✅ **ASGI integration** - Run FastAPI alongside Temporal workers
- ✅ **FastStream support** - Event-driven architectures
- ✅ **Production-ready** - Built-in logging, metrics, and graceful shutdown
- ✅ **Type-safe** - Full type hints and Pydantic integration

## Requirements

- Python >= 3.10
- Access to a Temporal server (local or remote)

## Installation

```bash
pip install temporal-boost
# or
poetry add temporal-boost
```

### Optional Extras

```bash
# FastStream integration
pip install "temporal-boost[faststream]"

# ASGI server support (choose one or more)
pip install "temporal-boost[uvicorn]"
pip install "temporal-boost[hypercorn]"
pip install "temporal-boost[granian]"
```

## Quick Start

```python
import logging
from datetime import timedelta
from temporalio import activity, workflow
from temporal_boost import BoostApp

logging.basicConfig(level=logging.INFO)

app = BoostApp(name="my-service")

@activity.defn(name="greet_activity")
async def greet_activity(name: str) -> str:
    return f"Hello, {name}!"

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

app.add_worker(
    "greeting_worker",
    "greeting_queue",
    activities=[greet_activity],
    workflows=[GreetingWorkflow],
)

if __name__ == "__main__":
    app.run()
```

Run your application:

```bash
# Start all workers
python3 main.py run all

# Or run a specific worker
python3 main.py run greeting_worker
```

## Configuration

All configuration is handled via environment variables. See the [Configuration Guide](https://northpowered.github.io/temporal-boost/configuration/) for complete details.

**Common settings:**

```bash
export TEMPORAL_TARGET_HOST=localhost:7233
export TEMPORAL_NAMESPACE=default
export TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
```

**Worker tuning:**

```bash
export TEMPORAL_MAX_CONCURRENT_ACTIVITIES=300
export TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=300
export TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
```

## Documentation

- 📖 [Getting Started](https://northpowered.github.io/temporal-boost/) - Overview and installation
- 🏗️ [Creating Applications](https://northpowered.github.io/temporal-boost/creating_application/) - Activities, workflows, and workers
- 🚀 [Running Applications](https://northpowered.github.io/temporal-boost/running_application/) - Deployment and production
- 🔧 [Configuration](https://northpowered.github.io/temporal-boost/configuration/) - Complete configuration reference
- 💡 [Examples](https://northpowered.github.io/temporal-boost/examples/) - Comprehensive examples and patterns
- 🎯 [Advanced Usage](https://northpowered.github.io/temporal-boost/advanced_usage/) - Customization and advanced features
- 📚 [API Reference](https://northpowered.github.io/temporal-boost/api_reference/) - Complete API documentation
- 🔍 [Troubleshooting](https://northpowered.github.io/temporal-boost/troubleshooting/) - Common issues and solutions

## Examples

```python
# CRON worker
app.add_worker(
    "daily_report",
    "report_queue",
    workflows=[DailyReportWorkflow],
    cron_schedule="0 0 * * *",
    cron_runner=DailyReportWorkflow.run,
)

# ASGI worker (FastAPI)
from fastapi import FastAPI
fastapi_app = FastAPI()
app.add_asgi_worker("api_worker", fastapi_app, "0.0.0.0", 8000)

# FastStream worker
from faststream import FastStream
faststream_app = FastStream(broker)
app.add_faststream_worker("message_worker", faststream_app)
```

See [Examples](https://northpowered.github.io/temporal-boost/examples/) for more patterns.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Links

- [Documentation](https://northpowered.github.io/temporal-boost/)
- [PyPI Package](https://pypi.org/project/temporal-boost/)
- [GitHub Repository](https://github.com/northpowered/temporal-boost)
- [Temporal Documentation](https://docs.temporal.io)
- [Temporal Python SDK](https://github.com/temporalio/sdk-python)
