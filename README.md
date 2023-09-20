# Temporal-boost
> Under active development

> Documentation in progress

Small framework based on [temporalio/sdk-python](https://github.com/temporalio/sdk-python) - create [Temporal](https://temporal.io/) microservices as fast as you can

# Quick start
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

# Usage: main.py [OPTIONS] COMMAND [ARGS]...

# Options:
#   --install-completion [bash|zsh|fish|powershell|pwsh]
#                                   Install completion for the specified shell.
#   --show-completion [bash|zsh|fish|powershell|pwsh]
#                                   Show completion for the specified shell, to
#                                   copy it or customize the installation.
#   --help                          Show this message and exit.

# Commands:
#   cron
#   run

```

```bash
python3 main.py run

# Usage: main.py run [OPTIONS] COMMAND [ARGS]...

# Options:
#   --help  Show this message and exit.

# Commands:
#   all
#   test_cron
#   worker_1
#   worker_2
```

```bash
python3 main.py run worker_1

# 2023-09-20T21:25:12 | INFO     | Worker worker_1 was registered in CLI
# 2023-09-20T21:25:12 | INFO     | Worker worker_2 was registered in CLI
# 2023-09-20T21:25:12 | INFO     | Worker test_cron was registered in CLI
# 2023-09-20T21:25:12 | INFO     | Worker worker_1 started on task_q_1 queue

```