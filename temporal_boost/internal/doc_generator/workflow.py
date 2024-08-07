import inspect as i
from typing import Any, List

from pydantic import BaseModel
from temporalio.workflow import _Definition

from .signal import SignalSchema


class WorkflowSchema(BaseModel):
    obj: Any
    workflow_worker: str
    signals: List[SignalSchema] | None = []

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
                <a class="workflows-nav-element" href="#workflow_{self.code_name}"><span class="badge bg-success">  </span> {self.code_name}</a>
            </li>
        """

    def html(self) -> str:
        # Signals block
        signals: str = "<h5>Signals:</h5><ul>"
        for signal in self.signals:
            signals = (
                signals
                + f"""<li><span class="badge bg-warning">Signal</span> <a href="#signal_{signal.code_name}">{signal.execution_name}</a></li>"""
            )

        signals = signals + "</ul>"

        if not len(self.definition.signals):
            signals = "<h5>No registered signals</h5>"
        # Executions args block
        execution_args: str = "<h5>Execution args:</h5><ul>"
        for arg in self.execution_args:
            if arg == "self":
                continue
            execution_args = execution_args + f"""<li>{self.execution_args.get(arg)}</a></li>"""
        execution_args = execution_args + "</ul>"
        # Ignoring `self`
        if len(self.execution_args) <= 1:
            execution_args = "<h5>No execution args</h5>"
        # Return block
        return_type = f"""<div><strong>Return: {str(self.definition.ret_type.__name__)}</strong></div>"""
        html_str: str = f"""
        <div id="workflow_{self.code_name}">
            <h4><span class="badge bg-success">Workflow</span> {self.code_name}</h4>
        </div>
        <div><span class="badge bg-secondary">Worker: {self.workflow_worker}</span></div>
        <p>
            <div><strong>Execution name: <i>{self.execution_name}</i></strong></div>
        </p>
        <div class="card">
            <div class="card-body text-dark">
                {self.obj.__doc__}
            </div>
        </div>
        {execution_args}
        {signals}
        {return_type}
        <br>
        """
        return html_str
