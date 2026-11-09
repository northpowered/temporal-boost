import sys
from unittest.mock import patch

import pytest
from temporalio.worker import Interceptor

from temporal_boost.temporal.worker import TemporalWorkerBuilder
from tests.cli_exit_app import make_app


@pytest.mark.parametrize("value", ["a path with spaces", "*.txt", "$TB_ARGUMENT", "%TB_ARGUMENT%", "~"])
def test_explicit_cli_arguments_are_literal(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TB_ARGUMENT", "expanded")
    app = make_app()
    arguments = ["exec", "greet", value]
    assert app.run(arguments, standalone_mode=False) == f"Hello {value}, count=1"
    assert arguments == ["exec", "greet", value]


def test_native_argv_uses_public_expansion_option(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["app.py", "exec", "greet", "a path with spaces"])
    assert make_app().run(standalone_mode=False, windows_expand_args=False) == "Hello a path with spaces, count=1"


@pytest.mark.skipif(sys.platform != "win32", reason="Requires actual Windows argument expansion")
def test_native_windows_expands_environment_and_explicit_list_stays_literal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TB_ARGUMENT", "expanded")
    monkeypatch.setattr(sys, "argv", ["app.py", "exec", "greet", "%TB_ARGUMENT%"])
    assert make_app().run(standalone_mode=False) == "Hello expanded, count=1"
    assert make_app().run(["exec", "greet", "%TB_ARGUMENT%"], standalone_mode=False) == "Hello %TB_ARGUMENT%, count=1"


def test_interceptor_uses_public_sdk_export_and_reaches_worker() -> None:
    interceptor = Interceptor()
    builder = TemporalWorkerBuilder("queue")
    builder.set_client(object())
    builder.set_interceptors([interceptor])
    with patch("temporal_boost.temporal.worker.Worker") as worker:
        builder.build()
    assert worker.call_args.kwargs["interceptors"] == [interceptor]
    assert worker.call_args.kwargs["interceptors"][0] is interceptor
