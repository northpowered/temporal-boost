import logging

from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel

from temporal_boost import BoostApp


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

faststream_logger = logger.getChild("faststream")


class TaskMessage(BaseModel):
    task_id: str
    description: str
    priority: int


broker = RedisBroker("redis://localhost:6379")
app = FastStream(broker)


@broker.subscriber("tasks")
async def process_task(message: TaskMessage) -> None:  # noqa: RUF029
    logger.info(f"Processing task: {message.task_id} - {message.description}")

    if message.priority > 5:  # noqa: PLR2004
        logger.info(f"High priority task {message.task_id} processed immediately")
    else:
        logger.info(f"Normal priority task {message.task_id} queued for processing")


boost_app = BoostApp("simple-faststream-example")
boost_app.add_faststream_worker("message_processor", app)


if __name__ == "__main__":
    boost_app.run()
