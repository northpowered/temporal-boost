from typing import List

from pydantic import BaseModel

from .worker import WorkerSchema


class MainSchema(BaseModel):
    workers: List[WorkerSchema] | None = []

    def nav(self) -> str:
        workers_nav: str = ""
        for w in self.workers:
            workers_nav = workers_nav + str(w.nav())

        return f""" <li>
                <a href="#workers" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle"><span class="badge bg-primary">Workers</span></a>
                <ul class="collapse list-unstyled" id="workers">
                    {workers_nav}
                </ul>
            </li>
            <li>
                <a href="#workflows" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle"><span class="badge bg-success">Workflows</span></a>
                <ul class="collapse list-unstyled" id="workflows">
                    
                </ul>
            </li>
            <li>
                <a href="#activities" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle"><span class="badge bg-info">Activities</span></a>
                <ul class="collapse list-unstyled" id="activities">
                    
                </ul>
            </li>"""

    def html(self) -> str:
        # Workers block
        workers_html: str = """<h2>Workers</h2><div class="line"></div>"""
        for w in self.workers:
            workers_html = workers_html + str(w.html())
        workers_html = workers_html + """<div class="line"></div>"""
        # Workflows block

        # Activities block

        return workers_html
