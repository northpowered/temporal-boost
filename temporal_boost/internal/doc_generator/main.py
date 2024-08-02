from typing import List

from pydantic import BaseModel

from .activity import ActivitySchema
from .signal import SignalSchema
from .typeschema import TypeSchema
from .worker import WorkerSchema
from .workflow import WorkflowSchema


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

        return f"""
          <li>
              <a href="#workers" data-bs-toggle="collapse" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle">
              <span class="badge bg-primary text-dark">Workers</span></a>
              <ul class="collapse list-unstyled" id="workers">
                  {workers_nav}
              </ul>
          </li>
          <li>
              <a href="#workflows" data-bs-toggle="collapse" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle">
              <span class="badge bg-success text-dark">Workflows</span></a>
              <ul class="collapse list-unstyled" id="workflows">
                  {workflows_nav}
              </ul>
          </li>
          <li>
              <a href="#activities" data-bs-toggle="collapse" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle">
              <span class="badge bg-info text-dark">Activities</span></a>
              <ul class="collapse list-unstyled" id="activities">
              {activities_nav}
              </ul>
          </li>
          <li>
              <a href="#signals" data-bs-toggle="collapse" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle">
              <span class="badge bg-warning text-dark">Signals</span></a>
              <ul class="collapse list-unstyled" id="signals">
                  {signals_nav}
              </ul>
          </li>
          <li>
              <a href="#schemas" data-bs-toggle="collapse" data-toggle="collapse" aria-expanded="false" class="dropdown-toggle">
              <span class="badge bg-danger text-dark">Schemas</span></a>
              <ul class="collapse list-unstyled" id="schemas">
                  {schemas_nav}
              </ul>
          </li>
            """

    def html(self) -> str:
        # Workers block
        workers_html: str = """"""
        for w in self.workers:
            workers_html = workers_html + str(w.html())

        # Workflows block
        workflows_html: str = """"""
        for w in self.workflows:
            workflows_html = workflows_html + str(w.html())

        # Activities block
        activities_html: str = """"""
        for a in self.activities:
            activities_html = activities_html + str(a.html())

        # Signals block
        signals_html: str = """"""
        for s in self.signals:
            signals_html = signals_html + str(s.html())

        # Schemas block
        schemas_html: str = """"""
        for s in self.schemas:
            schemas_html = schemas_html + str(s.html())

        result: str = f"""
            <div class="accordion accordion-flush accordion-dark" id="MainAccordion">

              <div class="accordion-item accordion-dark">
                <h2 class="accordion-header" id="flush-headingOne">
                  <button class="accordion-button collapsed accordion-dark" type="button"  id="workers-main-header">
                    Workers
                  </button>
                </h2>
                <div id="flush-workers" class="accordion-collapse collapse" aria-labelledby="flush-headingOne" data-bs-parent="#MainAccordion">
                  <div class="accordion-body">
                    {workers_html}
                  </div>
                </div>
              </div>

              <div class="accordion-item accordion-dark">
                <h2 class="accordion-header" id="flush-headingOne">
                  <button class="accordion-button collapsed accordion-dark" type="button" id="workflows-main-header">
                    Workflows
                  </button>
                </h2>
                <div id="flush-workflows" class="accordion-collapse collapse" aria-labelledby="flush-headingOne" data-bs-parent="#MainAccordion">
                  <div class="accordion-body">
                    {workflows_html}
                  </div>
                </div>
              </div>
              <div class="accordion-item accordion-dark">
                <h2 class="accordion-header" id="flush-headingOne">
                  <button class="accordion-button collapsed accordion-dark" type="button"  id="activities-main-header">
                    Activities
                  </button>
                </h2>
                <div id="flush-activities" class="accordion-collapse collapse" aria-labelledby="flush-headingOne" data-bs-parent="#MainAccordion">
                  <div class="accordion-body">
                    {activities_html}
                  </div>
                </div>
              </div>

              <div class="accordion-item accordion-dark">
                <h2 class="accordion-header" id="flush-headingOne">
                  <button class="accordion-button collapsed accordion-dark" type="button"  id="signals-main-header">
                    Signals
                  </button>
                </h2>
                <div id="flush-signals" class="accordion-collapse collapse" aria-labelledby="flush-headingOne" data-bs-parent="#MainAccordion">
                  <div class="accordion-body">
                    {signals_html}
                  </div>
                </div>
              </div>

              <div class="accordion-item accordion-dark">
                <h2 class="accordion-header" id="flush-headingOne">
                  <button class="accordion-button collapsed accordion-dark" type="button"  id="schemas-main-header">
                    Schemas
                  </button>
                </h2>
                <div id="flush-schemas" class="accordion-collapse collapse" aria-labelledby="flush-headingOne" data-bs-parent="#MainAccordion">
                  <div class="accordion-body">
                    {schemas_html}
                  </div>
                </div>
              </div>
            </div>
        """
        return result
