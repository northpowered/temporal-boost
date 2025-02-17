from pydantic import BaseModel

from .activity import ActivitySchema
from .signal import SignalSchema
from .typeschema import TypeSchema
from .worker import WorkerSchema
from .workflow import WorkflowSchema


class MainSchema(BaseModel):
    workers: list[WorkerSchema] | None = []
    workflows: list[WorkflowSchema] | None = []
    activities: list[ActivitySchema] | None = []
    signals: list[SignalSchema] | None = []
    schemas: list[TypeSchema] | None = []

    def nav(self) -> str:
        workers_nav: str = ""
        for worker in self.workers or []:
            workers_nav += str(worker.nav())

        workflows_nav: str = ""
        for workflow in self.workflows or []:
            workflows_nav += str(workflow.nav())

        activities_nav: str = ""
        for activity in self.activities or []:
            activities_nav += str(activity.nav())

        signals_nav: str = ""
        for signal in self.signals or []:
            signals_nav += str(signal.nav())

        schemas_nav: str = ""
        for schema in self.schemas or []:
            schemas_nav += str(schema.nav())

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
            """  # noqa: E501

    def html(self) -> str:
        # Workers block
        workers_html: str = """"""
        for worker in self.workers or []:
            workers_html += str(worker.html())

        # Workflows block
        workflows_html: str = """"""
        for workflow in self.workflows or []:
            workflows_html += str(workflow.html())

        # Activities block
        activities_html: str = """"""
        for activity in self.activities or []:
            activities_html += str(activity.html())

        # Signals block
        signals_html: str = """"""
        for signal in self.signals or []:
            signals_html += str(signal.html())

        # Schemas block
        schemas_html: str = """"""
        for schema in self.schemas or []:
            schemas_html += str(schema.html())

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
        """  # noqa: E501
        return result
