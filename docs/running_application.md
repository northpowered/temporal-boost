# Running application

Here is an example of a minimal app:

```python
# main.py
import logging
from temporal_boost import BoostApp

logging.basicConfig(level=logging.INFO)
app = BoostApp()

# Define your workflows and activities here
# ...

# Register workers
app.add_worker(
    "worker_1", "task_q_1", activities=[test_boost_activity_1, test_boost_activity_3],
)
app.add_worker("worker_2", "task_q_2", activities=[test_boost_activity_2])
app.add_worker("worker_3", "task_q_3", workflows=[MyWorkflow])

# Add ASGI worker (optional)
# app.add_asgi_worker("asgi_worker", fastapi_app, "0.0.0.0", 8000)

if __name__ == "__main__":
    app.run()
```

## Running in development

All workers will be started in separate processes by default:

```bash
python3 main.py run all
```

All configuration (Temporal endpoint, namespace, etc.) is handled via environment variables (see documentation).

## Running a specific worker

If you want to run a specific worker only, you can do so by providing its name as a command-line argument (if your app supports it):

```bash
python3 main.py run worker_1
```

Or for an ASGI worker:

```bash
python3 main.py run asgi_worker
```
