import socket
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def unit_tests_do_not_listen(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("integration") is not None:
        return

    def forbid_listen(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("Listening sockets require @pytest.mark.integration")

    monkeypatch.setattr(socket.socket, "listen", forbid_listen)
