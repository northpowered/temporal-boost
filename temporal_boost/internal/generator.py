import inspect as i
import typing

from temporalio.activity import _Definition as _ActivityDefinition
from temporalio.workflow import _Definition, _SignalDefinition

from temporal_boost.schemas import WorkerType

from .doc_generator import ActivitySchema, MainSchema, SignalSchema, TypeSchema, WorkerSchema, WorkflowSchema

if typing.TYPE_CHECKING:
    from temporal_boost.core import BoostApp


def generate_doc_schema(app: "BoostApp") -> MainSchema:
    schema: MainSchema = MainSchema()
    for worker in app.registered_workers:
        # Collecting only temporal workers
        # FUTURE: make universal doc generator
        if worker._type == WorkerType.TEMPORAL:
            schema.workers.append(
                WorkerSchema(
                    obj=worker,
                    worker_name=worker.name,
                    worker_queue=worker.task_queue,
                    worker_type=worker._type,
                    worker_description=worker.description,
                )
            )

            for workflow in worker.workflows:
                workflow_schema: WorkflowSchema = WorkflowSchema(obj=workflow, workflow_worker=worker.name)

                # Find content in workflow
                inspection: dict = dict(i.getmembers(workflow))
                definition: _Definition = inspection.get("__temporal_workflow_definition")
                # Find signals in workflow
                for signal_name in definition.signals:
                    signal: _SignalDefinition = definition.signals.get(signal_name)
                    signal_exec_inspection: dict = dict(i.getmembers(signal.fn))
                    signal_schema: SignalSchema = SignalSchema(
                        execution_name=signal_name,
                        code_name=signal.fn.__name__,
                        workflow_name=workflow.__name__,
                        signal_args=signal_exec_inspection.get("__annotations__"),
                        description=signal.fn.__doc__,
                    )
                    schema.signals.append(signal_schema)
                    workflow_schema.signals.append(signal_schema)

                schema.workflows.append(workflow_schema)

            for activity in worker.activities:
                inspection: dict = dict(i.getmembers(activity))
                definition: _ActivityDefinition = inspection.get("__temporal_activity_definition")
                fn_inspection: dict = dict(i.getmembers(definition.fn))
                for activity_schema in fn_inspection.get("__annotations__").values():
                    dataclass_fields: dict | None = dict(i.getmembers(activity_schema)).get("__dataclass_fields__")
                    if dataclass_fields:
                        schema.schemas.append(TypeSchema(name=activity_schema.__name__, fields=dataclass_fields))

                schema.activities.append(
                    ActivitySchema(
                        code_name=activity.__name__,
                        execution_name=definition.name,
                        description=activity.__doc__,
                        worker_name=worker.name,
                        execution_args=fn_inspection.get("__annotations__"),
                    )
                )
        schema.schemas = list(set(schema.schemas))

    return schema
