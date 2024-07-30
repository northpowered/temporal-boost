import inspect as i
from typing import Any

from pydantic import BaseModel
from temporalio.workflow import _Definition


class WorkflowSchema(BaseModel):
    obj: Any
    workflow_worker: str

    @property
    def inspection(self) -> dict:
        return dict(i.getmembers(self.obj))

    @property
    def definition(self) -> _Definition:
        return self.inspection.get("__temporal_workflow_definition")

    @property
    def code_name(self) -> str:
        return self.obj.__name__

    @property
    def execution_name(self) -> str:
        return self.definition.name

    @property
    def execution_args(self):
        return i.signature(self.definition.run_fn).parameters

    def nav(self) -> str:
        return f"""
            <li>
                <a href="#workflow_{self.code_name}"><span class="badge bg-success">Workflow</span> {self.code_name}</a>
            </li>
        """

    def html(self) -> str:
        # workflows: str = ""
        # activities: str = ""
        # if self.worker_type == WorkerType.TEMPORAL.value:
        #     workflows: str = "<h5>Workflows:</h5><ul>"
        #     for workflow in self.obj.workflows:
        #         workflows = workflows + f"""<li><a href="#workflow_{workflow.__name__}">{workflow.__name__}</a></li>"""
        #     workflows = workflows + "</ul><br>"
        #     if not len(self.obj.workflows):
        #         workflows = "<h5>No registered workflows</h5><br>"

        #     activities: str = "<h5>Activities:</h5><ul>"
        #     for activity in self.obj.activities:
        #         activities = activities + f"""<li><a href="#activity_{activity.__name__}">{activity.__name__}</a></li>"""
        #     activities = activities + "</ul>"
        #     if not len(self.obj.activities):
        #         activities = "<h5>No registered activities</h5>"


        html_str: str = f"""
        <div id="workflow_{self.code_name}"><h4><span class="badge bg-success">Workflow</span> {self.code_name}</h4></div>
        <div><span class="badge bg-secondary">Worker: {self.workflow_worker}</span></div>
        <div>Execution name: <i>{self.execution_name}</i></div>
        <div>{self.obj.__doc__}</div>
        <br>
        """
        # return html_str
        return html_str
