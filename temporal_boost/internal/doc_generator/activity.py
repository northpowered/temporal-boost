from typing import Any

from pydantic import BaseModel


class ActivitySchema(BaseModel):
    code_name: str
    execution_name: str
    worker_name: str
    execution_args: Any | None = None
    description: str | None = ""

    def nav(self) -> str:
        return f"""
            <li>
                <a class="activities-nav-element" href="#activity_{self.code_name}">
                <span class="badge bg-info">  </span> {self.execution_name}
                </a>
            </li>
        """

    def html(self) -> str:
        execution_args: str = "<h5>Execution args:</h5><ul>"
        for arg in self.execution_args:
            if arg == "return":
                execution_args = execution_args + f"""<strong>{arg}: {self.execution_args.get(arg).__name__}</a></strong>"""
            else:
                execution_args = execution_args + f"""<li>{arg}: {self.execution_args.get(arg).__name__}</a></li>"""
        execution_args = execution_args + "</ul>"
        if not len(self.execution_args):
            execution_args = "<h5>No execution args</h5>"

        html_str: str = f"""
        <div id="activity_{self.code_name}"><h4><span class="badge bg-info">Activity</span> {self.code_name}</h4></div>
        <div><span class="badge bg-secondary">Worker: {self.worker_name}</span></div>
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
