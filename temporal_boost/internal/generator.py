from .doc_generator import WorkerSchema, MainSchema, WorkflowSchema
import typing
from temporal_boost.schemas import WorkerType

if typing.TYPE_CHECKING:
    from temporal_boost.core import BoostApp


def generate_doc_schema(app: "BoostApp") -> MainSchema:
    schema: MainSchema = MainSchema()
    for worker in app.registered_workers:
        schema.workers.append(
            WorkerSchema(
                obj=worker,
                worker_name=worker.name,
                worker_queue=worker.task_queue,
                worker_type=worker._type,
                worker_description=worker.description,
            )
        )
        if worker._type == WorkerType.TEMPORAL:
            for workflow in worker.workflows:
                schema.workflows.append(WorkflowSchema(obj=workflow, workflow_worker=worker.name))

    return schema
