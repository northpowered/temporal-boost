from typing import Any

from pydantic import BaseModel

from temporal_boost.schemas import WorkerType


class WorkerSchema(BaseModel):
    obj: Any
    worker_name: str
    worker_queue: str
    worker_type: str
    worker_description: str

    def nav(self) -> str:
        return f"""
            <li>
                <a class="workers-nav-element" href="#worker_{self.worker_name}">
                <span class="badge bg-primary">  </span> {self.worker_name} </a>
            </li>
        """

    def html(self) -> str:
        workflows: str = ""
        activities: str = ""
        if self.worker_type == WorkerType.TEMPORAL.value:
            workflows: str = "<h5>Workflows:</h5><ul>"
            for workflow in self.obj.workflows:
                workflows = workflows + f"""<li><a href="#workflow_{workflow.__name__}">{workflow.__name__}</a></li>"""
            workflows = workflows + "</ul><br>"
            if not len(self.obj.workflows):
                workflows = "<h5>No registered workflows</h5><br>"

            activities: str = "<h5>Activities:</h5><ul>"
            for activity in self.obj.activities:
                activities = activities + f"""<li><a href="#activity_{activity.__name__}">{activity.__name__}</a></li>"""
            activities = activities + "</ul>"
            if not len(self.obj.activities):
                activities = "<h5>No registered activities</h5>"

        html_str: str = f"""
        <div id="worker_{self.worker_name}">
            <h4><span class="badge bg-primary">{self.worker_type}</span> {self.worker_name}</h4>
        </div>
        <div>
            <span class="badge bg-secondary">Queue: {self.worker_queue}</span>
        </div>
        <div>{self.worker_description}</div>
        {workflows}
        {activities}
        <br>
        """
        return html_str
