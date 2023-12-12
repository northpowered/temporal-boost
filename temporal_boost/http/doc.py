import pdoc
import subprocess
from pathlib import Path


def _build_html_doc(*modules: Path | str) -> str:
    """
    Uses pdoc to build html documentation
    for *modules*`

    Returns:
        str: HTML static doc page
    """
    html: str = pdoc.pdoc(modules)
    return html


def serve_doc_page(
    *modules: Path | str,
    host: str = "127.0.0.1",
    port: int = 8000,
    route: str = "/doc"
) -> int:

    html: str = _build_html_doc(modules)

    async def app(scope, receive, send):
        assert scope['type'] == 'http'

        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [
                [b'content-type', b'text/html'],
            ],
        })
        await send({
            'type': 'http.response.body',
            'body': html.encode(),
        })

    proc = subprocess.Popen(
        [
            "granian",
            "--host",
            host,
            "--port",
            port,
            "--interface",
            "asgi",
            "--url-path-prefix",
            route,
            "--threading-mode",
            "runtime",
            "--no-ws",
            "--loop",
            "asyncio",
            "doc:app"
        ],
        stdout=subprocess.DEVNULL
    )

    return proc.wait()
