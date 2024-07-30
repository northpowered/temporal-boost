from typing import List, Optional

from pydantic import BaseModel

from .worker import WorkerSchema
from .workflow import WorkflowSchema
from .signal import SignalSchema
from .activity import ActivitySchema
from .typeschema import TypeSchema


class MainSchema(BaseModel):
    workers: List[WorkerSchema] | None = []
    workflows: List[WorkflowSchema] | None = []
    activities: List[ActivitySchema] | None = []
    signals: List[SignalSchema] | None = []
    schemas: List[TypeSchema] | None = []

    def nav(self) -> str:
        workers_nav: str = ""
        for w in self.workers:
            workers_nav = workers_nav + str(w.nav())

        workflows_nav: str = ""
        for w in self.workflows:
            workflows_nav = workflows_nav + str(w.nav())

        activities_nav: str = ""
        for a in self.activities:
            activities_nav = activities_nav + str(a.nav())

        signals_nav: str = ""
        for s in self.signals:
            signals_nav = signals_nav + str(s.nav())

        schemas_nav: str = ""
        for s in self.schemas:
            schemas_nav = schemas_nav + str(s.nav())

        return f""" <li>
                <a href="#workers" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle"><span class="badge bg-primary text-dark">Workers</span></a>
                <ul class="collapse list-unstyled" id="workers">
                    {workers_nav}
                </ul>
            </li>
            <li>
                <a href="#workflows" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle"><span class="badge bg-success text-dark">Workflows</span></a>
                <ul class="collapse list-unstyled" id="workflows">
                    {workflows_nav}
                </ul>
            </li>
            <li>
                <a href="#activities" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle"><span class="badge bg-info text-dark">Activities</span></a>
                <ul class="collapse list-unstyled" id="activities">
                {activities_nav}
                </ul>
            </li>
            <li>
                <a href="#signals" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle"><span class="badge bg-warning text-dark">Signals</span></a>
                <ul class="collapse list-unstyled" id="signals">
                    {signals_nav}
                </ul>
            </li>
            <li>
                <a href="#schemas" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle"><span class="badge bg-danger text-dark">Schemas</span></a>
                <ul class="collapse list-unstyled" id="schemas">
                    {schemas_nav}
                </ul>
            </li>
            """

    def html(self) -> str:
        # Workers block
        workers_html: str = """<h2>Workers</h2><div class="line"></div>"""
        for w in self.workers:
            workers_html = workers_html + str(w.html())
        workers_html = workers_html + """<div class="line"></div>"""
        # Workflows block
        workflows_html: str = """<h2>Workflows</h2><div class="line"></div>"""
        for w in self.workflows:
            workflows_html = workflows_html + str(w.html())
        workflows_html = workflows_html + """<div class="line"></div>"""
        # Activities block
        activities_html: str = """<h2>Activities</h2><div class="line"></div>"""
        for a in self.activities:
            activities_html = activities_html + str(a.html())
        activities_html = activities_html + """<div class="line"></div>"""
        # Signals block
        signals_html: str = """<h2>Signals</h2><div class="line"></div>"""
        for s in self.signals:
            signals_html = signals_html + str(s.html())
        signals_html = signals_html + """<div class="line"></div>"""
        # Schemas block
        schemas_html: str = """<h2>Schemas</h2><div class="line"></div>"""
        for s in self.schemas:
            schemas_html = schemas_html + str(s.html())
        schemas_html = schemas_html + """<div class="line"></div>"""
        result = "".join([workers_html, workflows_html, activities_html, signals_html, schemas_html])

        return result
