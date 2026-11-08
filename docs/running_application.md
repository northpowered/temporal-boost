# Running application

This guide covers how to run Temporal-boost applications in development, testing, and production environments.

## Table of Contents

- [Development](#development)
- [Production Deployment](#production-deployment)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Process Management](#process-management)
- [Monitoring and Observability](#monitoring-and-observability)
- [Troubleshooting](#troubleshooting)

## Development

### Running All Workers

Start all registered workers in separate threads:

```bash
python3 main.py run all
```

This command will:

- Start all registered workers in separate threads
- Keep the process running until interrupted
- Coordinate SIGTERM/SIGINT shutdown for workers implementing the managed stop contract

Temporal workers configured with CRON parameters also run as consumers here. `run all` does not create
or register their server-side CRON chains; use `cron <name>` explicitly for each job that needs registration.

### Running Individual Workers

Run a specific worker by name:

```bash
python3 main.py run worker_name
```

Example:

```bash
python3 main.py run payment_worker
```

For a Temporal worker, this consumes its task queue, including tasks from a previously registered
CRON chain. It does not call `start_workflow()`, even when that worker has CRON configuration.

### Running CRON Workers

Start a CRON worker:

```bash
python3 main.py cron cron_worker_name
```

Example:

```bash
python3 main.py cron daily_report_cron
```

The command registers or reuses one server-side CRON chain and consumes its task queue. Keep the
same `cron_workflow_id` on every replica. The registration log contains the namespace, workflow ID,
and returned run ID. Repeated and concurrent starts reuse a running ID; a closed ID is rejected.
`run <name>` and `run all` consume queues without registering a CRON chain.

| Command | Consumes tasks | Registers a server-side CRON chain |
| --- | --- | --- |
| `run <name>` | Selected worker | No |
| `run all` | All registered workers | No |
| `cron <name>` | Selected CRON worker | Yes: starts or reuses its stable ID |

`cron <name>` exists only for workers with both `cron_schedule` and `cron_runner`. A partial pair or
an empty/whitespace-only expression is rejected with `ValueError` during application setup. Calling
`worker.cron()` directly on an ordinary consumer raises `RuntimeError` before opening a connection.
Fix older partial configurations by providing both parameters or omitting both.

Stopping the local process does not cancel, terminate, or delete the server-side CRON workflow.
It can continue executing through other consumers; without consumers, work waits on its queue.
Use Temporal Web or the Temporal client to cancel or terminate an identified chain when appropriate.
To permanently stop one, also disable its registrars; history retention eventually expires closed-ID
protection. Changing the ID creates a separate job. Changing the expression, type, or queue while
reusing an active ID does not change the existing chain.

### Migrating Existing UUID CRON Workflows

Earlier releases generated a fresh UUID on every `cron` start. The new stable default cannot discover
which old UUID belongs to a logical job, and deployment alone leaves those chains active. No workflow
is automatically cancelled or deleted.

1. Stop all old CRON registration processes and prevent the old deployment from restarting while
   migrating. Record the Temporal endpoint, namespace, workflow type, queue, and expected expression.
2. In Temporal Web, filter the namespace with, for example,
   `WorkflowType = 'DailyReportWorkflow' AND ExecutionStatus = 'Running'`.
   Inspect **all pages** of matching executions. Check each execution's task queue and its first
   `WorkflowExecutionStarted` history event's `cronSchedule`, together with business ownership.
   A UUID-shaped ID alone does not prove that a workflow is a duplicate. Inventory workflow IDs
   and current run IDs, and review closed history as well if a proposed ID may already exist.
3. To retain a known active chain, set `cron_workflow_id` to its existing UUID on every new replica.
   Cancel or terminate only the reviewed duplicate chains through Temporal Web or
   `client.get_workflow_handle(workflow_id).cancel()` / `.terminate(reason=...)`. Cancellation is
   cooperative: confirm each unwanted chain is closed and reconcile any in-flight business work.
4. Alternatively, move to a new explicit stable ID (or the documented default): stop and verify closure
   of **all** old chains for that job before registering the new ID. Coordinate in-flight work to
   prevent overlapping business effects. Never delete unrelated workflows based on a broad query.
5. Start the new deployment, compare its logged workflow ID with the inventory, and verify one
   active chain for the logical job. Repeat registration to confirm the same chain is reused.

Use the same deliberate procedure for schedule/type/queue changes. A closed ID is rejected while
its history is retained; use a reviewed new versioned ID when intentionally creating a replacement.

### Development Best Practices

1. **Use separate terminals**: Run each worker type in a separate terminal for easier debugging
2. **Enable debug logging**: Set `DEBUG` log level to see detailed execution logs
3. **Use local Temporal**: Run Temporal locally with Docker for development
4. **Hot reload**: Use tools like `watchdog` or `nodemon` for auto-restart during development

### Environment Setup

Create a `.env` file for development:

```bash
# .env
TEMPORAL_TARGET_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
TEMPORAL_MAX_CONCURRENT_ACTIVITIES=10
TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=10
```

Load with `python-dotenv`:

```python
from dotenv import load_dotenv
load_dotenv()
```

## Production Deployment

### Prerequisites

Before deploying to production:

1. **Temporal Server**: Ensure Temporal server/cluster is accessible
2. **Network**: Configure network access between workers and Temporal
3. **Environment Variables**: Set all required environment variables
4. **Monitoring**: Set up Prometheus metrics endpoint
5. **Logging**: Configure centralized logging (e.g., CloudWatch, Datadog)

### Environment Variables

Set production environment variables:

```bash
export TEMPORAL_TARGET_HOST=temporal.production.example.com:7233
export TEMPORAL_NAMESPACE=production
export TEMPORAL_TLS=true
export TEMPORAL_API_KEY=your-api-key-here
export TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
export TEMPORAL_MAX_CONCURRENT_ACTIVITIES=300
export TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=300
export TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
```

### Process Management

#### Using systemd

Create a systemd service file `/etc/systemd/system/temporal-worker.service`:

```ini
[Unit]
Description=Temporal Boost Worker
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/temporal-worker
Environment="TEMPORAL_TARGET_HOST=temporal.example.com:7233"
Environment="TEMPORAL_NAMESPACE=production"
ExecStart=/usr/bin/python3 /opt/temporal-worker/main.py run all
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable temporal-worker
sudo systemctl start temporal-worker
sudo systemctl status temporal-worker
```

#### Using supervisord

Create supervisord config `/etc/supervisor/conf.d/temporal-worker.conf`:

```ini
[program:temporal-worker]
command=/usr/bin/python3 /opt/temporal-worker/main.py run all
directory=/opt/temporal-worker
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/temporal-worker.err.log
stdout_logfile=/var/log/temporal-worker.out.log
environment=TEMPORAL_TARGET_HOST="temporal.example.com:7233",TEMPORAL_NAMESPACE="production"
```

Reload and start:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start temporal-worker
```

## Docker Deployment

### Basic Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV TEMPORAL_TARGET_HOST=localhost:7233
ENV TEMPORAL_NAMESPACE=default
ENV PYTHONUNBUFFERED=1

# Run application
CMD ["python", "main.py", "run", "all"]
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  temporal-worker:
    build: .
    environment:
      - TEMPORAL_TARGET_HOST=temporal:7233
      - TEMPORAL_NAMESPACE=default
      - TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
    depends_on:
      - temporal
    restart: unless-stopped

  temporal:
    image: temporalio/auto-setup:latest
    ports:
      - "7233:7233"
      - "8088:8088"
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
      - POSTGRES_SEEDS=postgresql
    depends_on:
      - postgresql

  postgresql:
    image: postgres:14
    environment:
      - POSTGRES_USER=temporal
      - POSTGRES_PASSWORD=temporal
      - POSTGRES_DB=temporal
    volumes:
      - temporal-db:/var/lib/postgresql/data

volumes:
  temporal-db:
```

Run:

```bash
docker-compose up -d
```

### Multi-stage Docker Build

Optimize Docker image size:

```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv export --locked --no-default-groups --no-emit-project --no-hashes --output-file requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run application
CMD ["python", "main.py", "run", "all"]
```

## Kubernetes Deployment

### Deployment Manifest

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: temporal-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: temporal-worker
  template:
    metadata:
      labels:
        app: temporal-worker
    spec:
      containers:
      - name: worker
        image: your-registry/temporal-worker:latest
        env:
        - name: TEMPORAL_TARGET_HOST
          value: "temporal.example.com:7233"
        - name: TEMPORAL_NAMESPACE
          value: "production"
        - name: TEMPORAL_USE_PYDANTIC_DATA_CONVERTER
          value: "true"
        - name: TEMPORAL_PROMETHEUS_BIND_ADDRESS
          value: "0.0.0.0:9090"
        ports:
        - containerPort: 9090
          name: metrics
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /metrics
            port: 9090
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /metrics
            port: 9090
          initialDelaySeconds: 10
          periodSeconds: 5
```

### Service for Metrics

```yaml
apiVersion: v1
kind: Service
metadata:
  name: temporal-worker-metrics
spec:
  selector:
    app: temporal-worker
  ports:
  - port: 9090
    targetPort: 9090
    name: metrics
```

### ConfigMap for Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: temporal-worker-config
data:
  TEMPORAL_TARGET_HOST: "temporal.example.com:7233"
  TEMPORAL_NAMESPACE: "production"
  TEMPORAL_USE_PYDANTIC_DATA_CONVERTER: "true"
```

### Using Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: temporal-credentials
type: Opaque
stringData:
  TEMPORAL_API_KEY: "your-api-key"
```

Reference in deployment:

```yaml
env:
- name: TEMPORAL_API_KEY
  valueFrom:
    secretKeyRef:
      name: temporal-credentials
      key: TEMPORAL_API_KEY
```

## Process Management

### Running Multiple Workers

For production, consider running workers separately:

```bash
# Terminal 1: Activity workers
python3 main.py run activity_worker

# Terminal 2: Workflow workers
python3 main.py run workflow_worker

# Terminal 3: CRON workers
python3 main.py cron daily_cron
```

Or use a process manager like PM2:

```bash
pm2 start "python3 main.py run activity_worker" --name activity-worker
pm2 start "python3 main.py run workflow_worker" --name workflow-worker
pm2 start "python3 main.py cron daily_cron" --name cron-worker
pm2 save
```

### Graceful Shutdown

`app.run_all_workers()` (also `python main.py run all`) coordinates cooperative shutdown.
When it runs in the main thread, SIGINT and SIGTERM request the same stop as `app.stop()`.
Previous signal handlers are restored when the coordinator exits, including on errors.
Repeated requests are safe and keep the original shutdown deadline.

`BoostApp(shutdown_timeout=30.0)` sets the total budget, in seconds, for stopping and joining
all started worker threads. The value must be finite and non-negative; zero allows no waiting.
The coordinator polls for stop requests at intervals of up to 50 ms, then requests all workers
to stop before joining them against one shared deadline. `request_stop()` implementations must
return promptly. If threads remain alive at the deadline, the coordinator reports `TimeoutError`
listing those workers. An earlier failure remains the raised exception; a subsequent timeout is logged.
Python cannot forcibly terminate threads: they remain daemon threads and
may continue running until process exit. Another run is rejected while those threads remain alive.

For programmatic use in a background thread, call `app.stop()` from another thread and wait for
`run_all_workers()` to return. No signal handlers are installed in this mode. `stop()` is non-blocking;
calling it before or after a run has no effect on the next run. Worker registration must finish
before starting the coordinator.

`run all` treats registered workers as long-running services. The first failure observed at a
worker's `run()` boundary requests application shutdown, stops the other started workers, and is
re-raised in the coordinator's calling thread after bounded cleanup. The original exception object
and traceback are preserved. Later worker failures, stop-request failures, and timeouts are logged
without replacing the first failure. Further workers are not started once a stop is observed.

A normal return before application shutdown is a `RuntimeError` naming the worker: the application
must not keep running with a missing service or report success after all workers exit unexpectedly.
Normal returns during shutdown succeed. `asyncio.CancelledError` and `concurrent.futures.CancelledError`
are normal only after application stop has been requested; otherwise they are failures. Other
exceptions, including `KeyboardInterrupt` and `SystemExit`, remain failures even during shutdown.

**Migration:** a finite custom worker that previously returned successfully from `run all` must now
call `app.stop()` before returning to request normal application completion, or use its individual
`run <name>` command. A worker-local stop alone does not request application shutdown. End-to-end
exit codes through `BoostApp.run()` and the external CLI remain tracked in TB-008/TB-009; the coordinator
itself propagates failures, and the Typer `run all` command propagates ordinary worker exceptions.

Workers participate by implementing `BaseBoostWorker.request_stop() -> bool`: a thread-safe,
non-blocking, repeatable request that also handles startup. Return `True` when supported.
The default returns `False`, which produces a warning. The coordinator never runs async
`shutdown()` in another event loop. Async workers can inherit `AsyncBoostWorker`, which owns
one loop per run, schedules stop requests onto it, calls `shutdown()` once on that loop, and
waits for `run_async()` to return. See the [custom worker example](advanced_usage.md#custom-worker-shutdown).

`TemporalBoostWorker` implements managed stopping for both normal execution and its local CRON runner.
`request_stop()` is safe from another thread and during startup. `run all` uses it to stop Temporal
workers alongside custom managed workers. Pending connection or CRON registration work is cancelled,
the local CRON wait is completed, and a running SDK worker is stopped and joined on its owning loop.
Startup failures preserve their original exception even if cleanup also fails. Sequential runs build
fresh SDK worker/client/runtime objects; concurrent normal and CRON runs on one adapter are rejected.

Async `worker.shutdown()` is safe before/after a run and repeatable on the owning loop. It requests stop
and waits for lifecycle completion; cancelling one shutdown waiter does not cancel cleanup. Calling it
from another active loop raises `RuntimeError`: use `worker.request_stop()` there. Worker callbacks
should also use the non-blocking request rather than awaiting their own shutdown.

FastStream, Uvicorn, Hypercorn, and Granian do not yet implement this managed stop contract (TB-013/TB-014).
Their existing cleanup paths may reach the coordinator's timeout. Individual `run <name>` and
`cron <name>` commands use adapter lifecycle directly; the application coordinator's signal handlers
apply to `run all`. The external CLI's multiple-process supervisor has its own behavior (TB-009).
Stopping a local CRON runner does not cancel or delete the server-side CRON workflow (TB-006).

The application budget is independent of the SDK's activity grace period. The worker builder now passes
`TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT` (integer seconds, default 30) to the SDK as `graceful_shutdown_timeout`.
An explicit `datetime.timedelta` passed to `app.add_worker(..., graceful_shutdown_timeout=...)` overrides
the environment, including zero; omission or `None` inherits it. Negative durations are rejected.

Once SDK shutdown starts, activities have that grace period before the SDK requests cancellation.
Zero skips the grace period. This is not a deadline for the whole SDK shutdown: it still waits for
activities, which may ignore cancellation. The option does not itself initiate shutdown.
It does not configure `BoostApp.shutdown_timeout`
or a process supervisor's deadline. Allow time for the SDK grace period plus cancellation and resource
cleanup within those budgets when using a managed adapter. See the
[configuration guide](configuration.md#temporal_graceful_shutdown_timeout) for an override example and migration details.

## Monitoring and Observability

### Prometheus Metrics

Enable Prometheus metrics:

```bash
export TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
```

Metrics will be available at `http://localhost:9090/metrics`.

### Key Metrics to Monitor

- `temporal_workflow_tasks_started` - Workflow tasks started
- `temporal_activity_tasks_started` - Activity tasks started
- `temporal_workflow_tasks_completed` - Completed workflow tasks
- `temporal_activity_tasks_completed` - Completed activity tasks
- `temporal_workflow_tasks_failed` - Failed workflow tasks
- `temporal_activity_tasks_failed` - Failed activity tasks

### Logging

Configure structured logging:

```python
import logging
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
app = BoostApp(logger_config=LOGGING_CONFIG)
```

### Health Checks

For ASGI workers, add a health endpoint:

```python
from fastapi import FastAPI

fastapi_app = FastAPI()

@fastapi_app.get("/health")
async def health():
    return {"status": "healthy"}
```

For Temporal workers, use Prometheus metrics endpoint as health check.

## Troubleshooting

### Worker Not Starting

**Problem**: Worker fails to start

**Solutions**:
1. Check Temporal server connectivity: `telnet temporal-host 7233`
2. Verify environment variables are set correctly
3. Check logs for connection errors
4. Ensure Temporal server is running and accessible

### Connection Timeout

**Problem**: Cannot connect to Temporal server

**Solutions**:
1. Verify `TEMPORAL_TARGET_HOST` is correct
2. Check network connectivity and firewall rules
3. For TLS, ensure `TEMPORAL_TLS=true`
4. Verify Temporal server is accepting connections

### Activities Not Executing

**Problem**: Activities are registered but not executing

**Solutions**:
1. Verify worker is connected to correct task queue
2. Check workflow is using correct task queue name
3. Ensure worker is running: `python3 main.py run worker_name`
4. Check Temporal UI for pending tasks

### Memory Issues

**Problem**: High memory usage

**Solutions**:
1. Reduce `TEMPORAL_MAX_CONCURRENT_ACTIVITIES`
2. Reduce `TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS`
3. Implement activity result size limits
4. Monitor memory usage with Prometheus

### Performance Issues

**Problem**: Slow workflow execution

**Solutions**:
1. Increase concurrency limits appropriately
2. Use separate task queues for different workloads
3. Optimize activity execution time
4. Monitor metrics for bottlenecks
5. Consider horizontal scaling (multiple workers)

### Debug Mode

Enable debug mode for detailed logging:

```python
app = BoostApp(debug_mode=True)
```

Or set environment variable:

```bash
export TEMPORAL_DEBUG=true
```

This will provide detailed execution logs and help identify issues.
