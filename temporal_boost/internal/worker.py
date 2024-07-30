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
    ) -> None:
        self.app = app
        self.name = "internal"
        self.task_queue = task_queue
        self.host: str = host
        self.port: int = port
        # Creating robyn app for internal web server
        robyn_config = config
        # Suppressing robyn rust logger
        config.log_level = "ERROR"
        self.web_app = Robyn("__internal__", config=robyn_config)
        self.web_app.add_route("GET", "/style.css", custom_css)
        self.web_app.add_route("GET", "/scripts.js", custom_js)
        self.web_app.add_route("GET", "/doc", self.build_html_doc)

        self.doc_schema = generate_doc_schema(self.app)

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
                    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.1.0/css/bootstrap.min.css" integrity="sha384-9gVQ4dYFwwWSjIDZnLEWnxCjeSWFphJiwGPXr1jddIhOegiu1FwO5qRGvFXOdJZ4" crossorigin="anonymous">
                    <link rel="stylesheet" href="/style.css">
                    <script defer src="https://use.fontawesome.com/releases/v5.0.13/js/solid.js" integrity="sha384-tzzSw1/Vo+0N5UhStP3bvwWPq+uvzCMfrN1fEFe+xBmv1C/AtVX5K0uZtmcHitFZ" crossorigin="anonymous"></script>
                    <script defer src="https://use.fontawesome.com/releases/v5.0.13/js/fontawesome.js" integrity="sha384-6OIrr52G08NpOFSZdxxz1xdNSndlD4vdcf/q2myIUVO0VsqaGHJsB0RaBE01VTOY" crossorigin="anonymous"></script>
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
                                    <a href="https://github.com/northpowered/temporal-boost" target="_blank" class="article">Temporal-boost on github</a>
                                </li>
                            </ul>
                        </nav>

                        <!-- Page Content  -->
                        <div id="content">
                            <h2>{self.app.name}</h2>
                            <p>Auto generated documentation</p>
                            {self.body}
                            <div class="line"></div>
                        </div>
                    </div>
                    <script src="https://code.jquery.com/jquery-3.3.1.slim.min.js" integrity="sha384-q8i/X+965DzO0rT7abK41JStQIAqVgRVzpbzo5smXKp4YfRvH+8abtTE1Pi6jizo" crossorigin="anonymous"></script>
                    <script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.14.0/umd/popper.min.js" integrity="sha384-cs/chFZiN24E4KMATLdqdvsezGxaGsi4hLGOzlXwp5UZB1LY//20VyM2taTB4QvJ" crossorigin="anonymous"></script>
                    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.1.0/js/bootstrap.min.js" integrity="sha384-uefMccjFJAIv6A+rW+L4AHf99KvxDjWSu1z9VI8SKNVmz4sk7buKt/6v9KI65qnm" crossorigin="anonymous"></script>
                    <script src="/scripts.js" type="text/javascript"></script>
                </body>

            </html>"""

        return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=content)

    def run(self):
        self.web_app.start(port=self.port, host=self.host)
        return self.worker_name
