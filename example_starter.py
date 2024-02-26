"""
For development purposes
"""

import asyncio
from temporalio.client import Client


async def main():

    client = await Client.connect("localhost:7233")

    # Run workflow
    result = await client.execute_workflow(
        "MyWorkflow",
        "blabla",
        id="pydantic_converter-workflow-id",
        task_queue="task_q_3",
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
