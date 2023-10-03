import pdoc
import subprocess
import granian

doc: str = pdoc.pdoc(
    "temporal_boost", "tests"
)


import granian

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
        'body': doc.encode(),
    })


# granian.server.Granian(
#     target="gen_doc:app",
#     port=8889,
#     interface="asgi"
# ).serve()


proc = subprocess.Popen(
    [
        "granian",
        "--port",
        "8889",
        "--interface",
        "asgi",
        "--threading-mode",
        "runtime",
        "--no-ws",
        "--loop",
        "asyncio",
        "gen_doc:app"
    ],
    stdout=subprocess.DEVNULL
)

proc.wait()


