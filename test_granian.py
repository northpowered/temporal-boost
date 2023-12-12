import asyncio
from functools import partial
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
        'body': 'qwerty',
    })

async def _server(interface, port, threading_mode, tls=False):

    proc = await asyncio.create_subprocess_shell(
        ''.join(
            [
                f'granian --interface {interface} --port {port} ',
                f'--threads 1 --threading-mode {threading_mode} ',
                f'test_granian:app',
            ]
        ),
    )
    await proc.wait()
    # await asyncio.sleep(1)
    # try:
    #     yield port
    # finally:
    #     proc.terminate()
    #     await proc.wait()

asyncio.run(_server("asgi", 8888, "runtime"))
