"""
Error handling and retry example for Temporal-boost.

This example demonstrates:
- Custom retry policies for activities
- Error handling in workflows
- Activity heartbeat for long-running tasks
- Graceful error recovery

Run with: python3 example_error_handling.py run worker
"""

import asyncio
import logging
import random
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporal_boost import BoostApp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BoostApp(name="error-handling-example")

# Simulate transient errors
class TransientError(Exception):
    """Error that should be retried."""
    pass

class PermanentError(Exception):
    """Error that should not be retried."""
    pass

@activity.defn(
    name="unreliable_api_call",
    start_to_close_timeout=timedelta(seconds=30),
    retry_policy=RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=60),
        maximum_attempts=5,
    ),
)
async def unreliable_api_call(url: str) -> dict:
    """Activity with custom retry policy that may fail."""
    logger.info(f"Calling API: {url}")
    
    # Simulate random failures (30% chance)
    if random.random() < 0.3:
        logger.warning(f"API call failed for {url}, will retry")
        raise TransientError(f"Temporary failure for {url}")
    
    # Simulate permanent errors (5% chance)
    if random.random() < 0.05:
        logger.error(f"Permanent error for {url}")
        raise PermanentError(f"Permanent failure for {url}")
    
    logger.info(f"API call succeeded for {url}")
    return {"url": url, "status": "success", "data": "some data"}

@activity.defn(
    name="long_running_task",
    start_to_close_timeout=timedelta(minutes=10),
    retry_policy=RetryPolicy(maximum_attempts=3),
)
async def long_running_task(task_id: str, duration: int) -> dict:
    """Long-running activity with heartbeat."""
    logger.info(f"Starting long-running task {task_id}")
    
    for i in range(duration):
        await asyncio.sleep(1)
        # Send heartbeat to keep activity alive
        activity.heartbeat(f"Progress: {i}/{duration}")
        logger.debug(f"Task {task_id} progress: {i}/{duration}")
    
    logger.info(f"Completed long-running task {task_id}")
    return {"task_id": task_id, "status": "completed", "duration": duration}

@workflow.defn(sandboxed=False, name="ErrorHandlingWorkflow")
class ErrorHandlingWorkflow:
    """Workflow demonstrating error handling patterns."""
    
    @workflow.run
    async def run(self, url: str, task_id: str) -> dict:
        """Execute workflow with error handling."""
        logger.info(f"Starting workflow for {url}")
        
        # Try API call with automatic retries
        try:
            api_result = await workflow.execute_activity(
                unreliable_api_call,
                url,
                task_queue="error_queue",
                start_to_close_timeout=timedelta(minutes=5),
            )
            logger.info(f"API call succeeded: {api_result}")
        except PermanentError as e:
            logger.error(f"Permanent error occurred: {e}")
            return {
                "status": "failed",
                "reason": "permanent_error",
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                "status": "failed",
                "reason": "unexpected_error",
                "error": str(e),
            }
        
        # Execute long-running task
        try:
            task_result = await workflow.execute_activity(
                long_running_task,
                task_id,
                10,  # 10 seconds
                task_queue="error_queue",
                start_to_close_timeout=timedelta(minutes=10),
            )
            logger.info(f"Long-running task completed: {task_result}")
        except Exception as e:
            logger.error(f"Long-running task failed: {e}")
            # Continue workflow even if task fails
            task_result = {"status": "failed", "error": str(e)}
        
        return {
            "status": "completed",
            "api_result": api_result,
            "task_result": task_result,
        }

app.add_worker(
    "worker",
    "error_queue",
    activities=[unreliable_api_call, long_running_task],
    workflows=[ErrorHandlingWorkflow],
)

if __name__ == "__main__":
    app.run()

