# Troubleshooting

Common issues and solutions when working with Temporal-boost.

## Table of Contents

- [Connection Issues](#connection-issues)
- [Worker Issues](#worker-issues)
- [Activity Issues](#activity-issues)
- [Workflow Issues](#workflow-issues)
- [Performance Issues](#performance-issues)
- [Configuration Issues](#configuration-issues)
- [Deployment Issues](#deployment-issues)

## Connection Issues

### Cannot Connect to Temporal Server

**Symptoms:**
- Connection timeout errors
- "Connection refused" errors
- Worker fails to start

**Solutions:**

1. **Verify Temporal server is running:**
   ```bash
   telnet temporal-host 7233
   ```

2. **Check environment variables:**
   ```bash
   echo $TEMPORAL_TARGET_HOST
   echo $TEMPORAL_NAMESPACE
   ```

3. **Verify network connectivity:**
   ```bash
   ping temporal-host
   curl -v temporal-host:7233
   ```

4. **Check firewall rules:**
   - Ensure port 7233 is open
   - Check security group settings

5. **For TLS connections:**
   ```bash
   export TEMPORAL_TLS=true
   export TEMPORAL_API_KEY=your-api-key
   ```

### TLS Handshake Errors

**Symptoms:**
- SSL/TLS errors
- Certificate validation failures

**Solutions:**

1. **Verify TLS configuration:**
   ```python
   # Check if TLS is enabled
   import os
   print(os.getenv("TEMPORAL_TLS"))
   ```

2. **For Temporal Cloud:**
   - Ensure `TEMPORAL_API_KEY` is set
   - Verify API key is valid

3. **For self-hosted with TLS:**
   - Verify certificate configuration
   - Check certificate expiration

## Worker Issues

### Worker Not Starting

**Symptoms:**
- Worker fails to initialize
- No tasks being processed

**Solutions:**

1. **Check worker registration:**
   ```python
   workers = app.get_registered_workers()
   for worker in workers:
       print(worker.name)
   ```

2. **Verify worker configuration:**
   ```python
   worker = app.add_worker("test", "test_queue", activities=[...])
   print(worker.name)
   ```

3. **Check for reserved names:**
   - Don't use: "run", "cron", "exec", "all"
   - Use descriptive, unique names

4. **Verify activities/workflows are defined:**
   ```python
   # Ensure at least one activity or workflow
   if not activities and not workflows:
       raise ValueError("Worker must have activities or workflows")
   ```

### Worker Not Processing Tasks

**Symptoms:**
- Worker is running but no tasks processed
- Tasks stuck in queue

**Solutions:**

1. **Verify task queue name matches:**
   ```python
   # In workflow
   await workflow.execute_activity(
       my_activity,
       data,
       task_queue="my_queue",  # Must match worker queue
   )
   ```

2. **Check worker is connected:**
   - Look for connection logs
   - Verify Temporal server is accessible

3. **Check task queue in Temporal UI:**
   - Verify tasks are in the queue
   - Check for pending tasks

4. **Verify activity/workflow names:**
   ```python
   @activity.defn(name="my_activity")  # Must match
   async def my_activity(...):
       ...
   ```

## Activity Issues

### Activity Not Found

**Symptoms:**
- "Activity not found" errors
- Activity not executing

**Solutions:**

1. **Verify activity name matches:**
   ```python
   @activity.defn(name="my_activity")
   async def my_activity(...):
       ...
   
   # In workflow, use the function, not string
   await workflow.execute_activity(
       my_activity,  # Use function, not "my_activity"
       data,
   )
   ```

2. **Check activity is registered:**
   ```python
   app.add_worker(
       "worker",
       "queue",
       activities=[my_activity],  # Must include activity
   )
   ```

3. **Verify task queue matches:**
   - Activity must be in worker on same queue

### Activity Timeout

**Symptoms:**
- Activity timeout errors
- "Activity timeout" messages

**Solutions:**

1. **Increase timeout:**
   ```python
   await workflow.execute_activity(
       my_activity,
       data,
       start_to_close_timeout=timedelta(minutes=10),  # Increase timeout
   )
   ```

2. **Check activity execution time:**
   - Log activity start/end times
   - Optimize slow operations

3. **Use heartbeat for long-running activities:**
   ```python
   @activity.defn(name="long_activity")
   async def long_activity(data: str) -> str:
       for i in range(100):
           await asyncio.sleep(1)
           activity.heartbeat(f"Progress: {i}%")
       return "Done"
   ```

### Activity Retry Issues

**Symptoms:**
- Activities retrying indefinitely
- No retries happening

**Solutions:**

1. **Configure retry policy:**
   ```python
   @activity.defn(
       name="retryable_activity",
       retry_policy=RetryPolicy(
           maximum_attempts=3,
           initial_interval=timedelta(seconds=1),
       ),
   )
   async def retryable_activity(...):
       ...
   ```

2. **Check error types:**
   - Temporal errors are retried
   - Application errors may not be retried

## Workflow Issues

### Workflow Not Starting

**Symptoms:**
- Workflow not executing
- No workflow runs

**Solutions:**

1. **Verify workflow is registered:**
   ```python
   app.add_worker(
       "worker",
       "queue",
       workflows=[MyWorkflow],  # Must include workflow
   )
   ```

2. **Check workflow name:**
   ```python
   @workflow.defn(name="MyWorkflow")
   class MyWorkflow:
       ...
   ```

3. **Verify client connection:**
   ```python
   client = await Client.connect("localhost:7233")
   await client.start_workflow(
       "MyWorkflow",  # Must match @workflow.defn name
       data,
       task_queue="queue",
   )
   ```

### Workflow Determinism Errors

**Symptoms:**
- "Non-deterministic workflow" errors
- Workflow execution failures

**Solutions:**

1. **Don't use random:**
   ```python
   # ❌ Wrong
   import random
   value = random.randint(1, 10)
   
   # ✅ Correct
   value = workflow.random().randint(1, 10)
   ```

2. **Don't use datetime.now():**
   ```python
   # ❌ Wrong
   from datetime import datetime
   now = datetime.now()
   
   # ✅ Correct
   now = workflow.now()
   ```

3. **Don't perform I/O:**
   ```python
   # ❌ Wrong
   import httpx
   response = httpx.get("https://api.example.com")
   
   # ✅ Correct - Use activity
   response = await workflow.execute_activity(
       fetch_data,
       task_queue="api_queue",
   )
   ```

### Workflow Timeout

**Symptoms:**
- Workflow execution timeout
- Long-running workflows fail

**Solutions:**

1. **Use continue-as-new for long workflows:**
   ```python
   @workflow.defn(sandboxed=False, name="LongWorkflow")
   class LongWorkflow:
       @workflow.run
       async def run(self, data: list) -> None:
           for i, item in enumerate(data):
               if i > 0 and i % 100 == 0:
                   await workflow.continue_as_new(data[i:])
               await workflow.execute_activity(
                   process_item,
                   item,
                   task_queue="queue",
               )
   ```

2. **Split into multiple workflows:**
   - Break long workflows into smaller ones
   - Use child workflows

## Performance Issues

### High Memory Usage

**Symptoms:**
- Memory usage growing
- Out of memory errors

**Solutions:**

1. **Reduce concurrency:**
   ```bash
   export TEMPORAL_MAX_CONCURRENT_ACTIVITIES=100
   export TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=100
   ```

2. **Limit activity result size:**
   - Don't return large objects
   - Use external storage for large data

3. **Monitor memory:**
   ```python
   import psutil
   process = psutil.Process()
   print(f"Memory: {process.memory_info().rss / 1024 / 1024} MB")
   ```

### Slow Workflow Execution

**Symptoms:**
- Workflows taking too long
- Low throughput

**Solutions:**

1. **Increase concurrency:**
   ```bash
   export TEMPORAL_MAX_CONCURRENT_ACTIVITIES=500
   export TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=300
   ```

2. **Use parallel activities:**
   ```python
   results = await asyncio.gather(
       workflow.execute_activity(activity1, data1),
       workflow.execute_activity(activity2, data2),
   )
   ```

3. **Optimize activity execution:**
   - Reduce I/O operations
   - Use connection pooling
   - Cache results when appropriate

4. **Use sticky workflows:**
   ```python
   worker = app.add_worker(
       "worker",
       "queue",
       workflows=[MyWorkflow],
       nonsticky_to_sticky_poll_ratio=0.1,  # Prefer sticky
   )
   ```

## Configuration Issues

### Environment Variables Not Loading

**Symptoms:**
- Configuration not applied
- Using default values

**Solutions:**

1. **Verify environment variables:**
   ```bash
   env | grep TEMPORAL
   ```

2. **Load from .env file:**
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

3. **Check variable names:**
   - Use exact names: `TEMPORAL_TARGET_HOST`
   - Case-sensitive

4. **Verify in code:**
   ```python
   from temporal_boost.temporal import config
   print(config.TARGET_HOST)
   ```

### Prometheus Metrics Not Working

**Symptoms:**
- Metrics endpoint not accessible
- No metrics collected

**Solutions:**

1. **Verify bind address:**
   ```bash
   export TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
   ```

2. **Check port availability:**
   ```bash
   netstat -an | grep 9090
   ```

3. **Verify endpoint:**
   ```bash
   curl http://localhost:9090/metrics
   ```

4. **Check runtime configuration:**
   ```python
   worker.configure_temporal_runtime(
       prometheus_bind_address="0.0.0.0:9090",
   )
   ```

## Deployment Issues

### Docker Container Issues

**Symptoms:**
- Container not starting
- Connection errors in container

**Solutions:**

1. **Check network configuration:**
   ```yaml
   # docker-compose.yml
   services:
     worker:
       network_mode: "host"  # Or use proper network
   ```

2. **Verify environment variables:**
   ```yaml
   environment:
     - TEMPORAL_TARGET_HOST=temporal:7233
   ```

3. **Check logs:**
   ```bash
   docker logs container_name
   ```

### Kubernetes Deployment Issues

**Symptoms:**
- Pods not starting
- Connection errors

**Solutions:**

1. **Verify service connectivity:**
   ```yaml
   env:
     - name: TEMPORAL_TARGET_HOST
       value: "temporal-service:7233"
   ```

2. **Check DNS resolution:**
   ```bash
   kubectl exec -it pod-name -- nslookup temporal-service
   ```

3. **Verify secrets:**
   ```yaml
   env:
     - name: TEMPORAL_API_KEY
       valueFrom:
         secretKeyRef:
           name: temporal-secrets
           key: api-key
   ```

## Debugging Tips

### Enable Debug Mode

```python
app = BoostApp(debug_mode=True)
```

Or:

```bash
export TEMPORAL_DEBUG=true
```

### Enable Verbose Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Temporal UI

- Access Temporal UI at `http://localhost:8088`
- View running workflows
- Check task queues
- Inspect workflow history

### Common Log Patterns

```python
# Log worker startup
logger.info(f"Worker {worker.name} starting")

# Log activity execution
logger.info(f"Executing activity: {activity_name}")

# Log workflow state
logger.info(f"Workflow state: {workflow_state}")
```

### Getting Help

If issues persist:

1. Check [Temporal documentation](https://docs.temporal.io)
2. Review [Temporal Python SDK docs](https://python.temporal.io)
3. Check GitHub issues: [temporal-boost issues](https://github.com/northpowered/temporal-boost/issues)
4. Enable debug logging and review logs
5. Check Temporal server logs

