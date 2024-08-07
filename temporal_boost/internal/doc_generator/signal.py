from typing import Any

from pydantic import BaseModel


class SignalSchema(BaseModel):
    code_name: str
    execution_name: str
    signal_args: Any | None = None
    workflow_name: str | None = None
    description: str | None = ""

    def nav(self) -> str:
        return f"""
            <li>
                <a class="signals-nav-element" href="#signal_{self.code_name}">
                    <span class="badge bg-warning">  </span> {self.execution_name}
                </a>
            </li>
        """

    def html(self) -> str:
        execution_args: str = "<h5>Execution args:</h5><ul>"
        for arg in self.signal_args:
            if arg == "self":
                continue
            execution_args = execution_args + f"""<li>{arg}: {self.signal_args.get(arg).__name__}</a></li>"""
        execution_args = execution_args + "</ul>"
        if not len(self.signal_args):
            execution_args = "<h5>No execution args</h5>"

        html_str: str = f"""
        <div id="signal_{self.code_name}"><h4><span class="badge bg-warning">Signal</span> {self.code_name}</h4></div>
            <div><span class="badge bg-secondary">Workflow: {self.workflow_name}</span></div>
            <p>
                <div><strong>Execution name: <i>{self.execution_name}</i></strong></div>
            </p>
            <div class="card">
                <div class="card-body text-dark">
                    {self.description}
                </div>
            </div>
        {execution_args}
        <br>
        """
        return html_str
