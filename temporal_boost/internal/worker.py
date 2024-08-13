import typing

from robyn import Response, Robyn, config

from temporal_boost.schemas import WorkerType

from .endpoints import custom_css, custom_js
from .generator import generate_doc_schema

if typing.TYPE_CHECKING:
    from temporal_boost.core import BoostApp


class InternalWorker:
    def __init__(
        self,
        app: "BoostApp",
        task_queue: str,
        worker_name: str,
        host: str,
        port: int,
        doc_endpoint: str | None = "/doc",
        doc_css_endpoint: str | None = "/style.css",
        doc_js_endpoint: str | None = "/scripts.js",
    ) -> None:
        self.app = app
        self.name = worker_name
        self.task_queue = task_queue
        self.host: str = host
        self.port: int = port
        self.doc_endpoint: str | None = doc_endpoint
        # Creating robyn app for internal web server
        robyn_config = config
        # Suppressing robyn rust logger
        config.log_level = "ERROR"

        self._local_css_endpoint: str = doc_css_endpoint
        self._local_js_endpoint: str = doc_js_endpoint

        self.web_app = Robyn("__internal__", config=robyn_config)

        if self.doc_endpoint:
            self.web_app.add_route("GET", self._local_css_endpoint, custom_css)
            self.web_app.add_route("GET", self._local_js_endpoint, custom_js)
            self.web_app.add_route("GET", self.doc_endpoint, self.build_html_doc, is_const=True)

        self.doc_schema = generate_doc_schema(self.app)
        self.rendered_doc: str | None = None
        self._type: WorkerType = WorkerType.INTERNAL
        self.description: str = ""  # create arg

    @property
    def nav(self) -> str:
        return self.doc_schema.nav()

    @property
    def body(self) -> str:
        return self.doc_schema.html()

    async def build_html_doc(self):
        content: str = f"""
            <!DOCTYPE html>
            <html>
                <head>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <meta http-equiv="X-UA-Compatible" content="IE=edge">
                    <title>{self.app.name}</title>
                    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
                    <link rel="stylesheet" href="{self._local_css_endpoint}">
                    <script defer src="https://use.fontawesome.com/releases/v5.0.13/js/solid.js"></script>
                    <script defer src="https://use.fontawesome.com/releases/v5.0.13/js/fontawesome.js"></script>
                </head>
                <body>
                    <div class="wrapper">
                        <!-- Sidebar  -->
                        <nav id="sidebar">
                            <div class="sidebar-header">
                                <h3>Temporal boost doc</h3>
                            </div>
                            <ul class="list-unstyled components">
                                {self.nav}
                            </ul>
                            <ul class="list-unstyled CTAs">
                                <li>
                                    <a href="https://github.com/northpowered/temporal-boost" target="_blank" class="article">Temporal-boost on github
                                    </a>
                                </li>
                            </ul>
                        </nav>

                        <!-- Page Content  -->
                        <div id="content">
                            <h2>{self.app.name}</h2>
                            <p>Auto generated documentation (Alpha version)</p>
                            {self.body}
                            <div class="line"></div>
                        </div>
                    </div>
                    <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.2/dist/umd/popper.min.js"></script>
                    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.min.js"></script>
                    <script src="https://code.jquery.com/jquery-3.3.1.slim.min.js"></script>
                    <script src="{self._local_js_endpoint}" type="text/javascript"></script>
                </body>
            </html>"""

        return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=content)

    def run(self):
        self.web_app.start(port=self.port, host=self.host)
        return self.worker_name
