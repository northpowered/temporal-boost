"""
Basic starter example for Temporal-boost.

This example demonstrates:
- Creating a BoostApp
- Defining activities and workflows
- Registering workers
- Running the application

Run with: python3 example_starter.py run all
"""

import logging
from datetime import timedelta

from temporalio import activity, workflow

from temporal_boost import BoostApp


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the application
app = BoostApp(name="starter-example")


# Define an activity
@activity.defn(name="greet_activity")
async def greet_activity(name: str) -> str:
    """A simple activity that greets someone."""
    logger.info(f"Greeting {name}")
    return f"Hello, {name}!"


# Define a workflow
@workflow.defn(sandboxed=False, name="GreetingWorkflow")
class GreetingWorkflow:
    """A simple workflow that executes a greeting activity."""

    @workflow.run
    async def run(self, name: str) -> str:
        """Main workflow execution method."""
        logger.info(f"Starting workflow for {name}")

        result = await workflow.execute_activity(
            greet_activity,
            name,
            task_queue="greeting_queue",
            start_to_close_timeout=timedelta(minutes=1),
        )

        logger.info(f"Workflow completed: {result}")
        return result


# Register a worker that handles both activities and workflows
app.add_worker(
    "greeting_worker",
    "greeting_queue",
    activities=[greet_activity],
    workflows=[GreetingWorkflow],
)

if __name__ == "__main__":
    app.run()
