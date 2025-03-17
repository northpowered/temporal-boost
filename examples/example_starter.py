import asyncio

from temporalio.client import Client


async def main() -> None:
    client = await Client.connect("localhost:7233")

    # Run workflow
    await client.execute_workflow(
        "MyCustomFlowName",
        "blabla",
        id="pydantic_converter-workflow-id",
        task_queue="task_q_3",
    )


if __name__ == "__main__":
    asyncio.run(main())
