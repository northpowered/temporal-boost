# Running application

Here the example of our app:

```python
# main.py
from temporal_boost import BoostApp

app: BoostApp = BoostApp()

# Some workflows or activities
# ...
# Some FastAPI app
# ...

# Temporal workers
app.add_worker(
    "worker_1", "task_q_1", activities=[test_boost_activity_1, test_boost_activity_3],
)
app.add_worker("worker_2", "task_q_2", activities=[test_boost_activity_2])

app.add_worker("worker_3", "task_q_3", workflows=[MyWorkflow])

# Cron worker
app.add_worker("worker_4", "task_q_4", workflows=[MyWorkflow], cron_runner=MyWorkflow.run, cron_schedule="* * * * *")

# FastAPI worker
app.add_asgi_worker("asgi_worker", fastapi_app, "0.0.0.0", 8000)

# Internal worker
app.add_internal_worker("0.0.0.0", 8888, doc_endpoint="/doc")

app.run()
```

## Running in dev mode

In `dev` mode all workers (except crons) can be started with one command in multiprocess mode:

```bash
python3 main.py run all
```
!!! warning annotate "Never use this way in production!"

## Running workers one-by-one

Also, you can run each worker by name:

```bash
python3 main.py run worker_1

python3 main.py run asgi_worker
```

To run cron worker, use this command:

```bash
python3 main.py cron worker_4
```
