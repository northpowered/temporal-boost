# Creating application

## Base code example

```python
# Creating `BoostApp` object

from temporal_boost import BoostApp, BoostLoggerConfig, BoostOTLPConfig

app: BoostApp = BoostApp(
    name="BoostApp example", # Name of the service
    temporal_endpoint="localhost:7233", # Temporal endpoint
    temporal_namespace="default", # Temporal namespace
    logger_config=BoostLoggerConfig(
        json=True, # Serialize logs in JSON format
        bind_extra={"foo": "bar",}, # Add global `extra` for JSON logs
        level="DEBUG", # Log level
        multiprocess_safe=True # Enqueue mode of loguru
    ),    
    otlp_config=BoostOTLPConfig(
        otlp_endpoint="otlp-collector", # OTLP reciever endpoint
        service_name="example-app" #  Service name for OTLP
    ),
    use_pydantic=True # Use special JSON serializer inside Temporal SDK
)
```
### BoostLoggerConfig

### BoostOTLPConfig

## Adding temporal workers

### Examples
```python
app.add_worker(
    "my_worker_1",
    "my_queue_1",
    activities=[my_activity],
    metrics_endpoint="0.0.0.0:9000",
    description="This workers serves activity my_activity on my_queue_1 and metrics endpoint"
)
app.add_worker(
    "worker_2",
    "my_queue_2",
    workflows=[MyWorkflow],
    description="This workers serves workflow MyWorkflow on my_queue_2"
)
app.add_worker(
    "worker_3",
    "my_queue_3",
    workflows=[MyWorkflow2],
    activities=[my_activity2],
    description="This workers serves workflow MyWorkflow3 and activity my_activity2 on my_queue_3"
)

```

## Adding CRON workers

## Adding internal worker

## Adding ASGI workers