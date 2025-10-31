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
- Handle graceful shutdown on SIGTERM/SIGINT

### Running Individual Workers

Run a specific worker by name:

```bash
python3 main.py run worker_name
```

Example:

```bash
python3 main.py run payment_worker
```

### Running CRON Workers

Start a CRON worker:

```bash
python3 main.py cron cron_worker_name
```

Example:

```bash
python3 main.py cron daily_report_cron
```

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
RUN pip install --user poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

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

Temporal-boost handles graceful shutdown automatically:

- Workers receive SIGTERM/SIGINT
- Running activities complete (up to `TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT`)
- New tasks are not accepted
- Connections are closed cleanly

Default timeout is 30 seconds (configurable via `TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT`).

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
