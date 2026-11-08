import subprocess  # noqa: S404
import sys
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from typer.testing import CliRunner

from temporal_boost import BoostApp
from temporal_boost.cli.runner import cli_app
from tests.cli_exit_app import ExitCodeWorker, make_app


CASES = [
    ([], 2, "Usage:"),
    (["--help"], 0, "Usage:"),
    (["run", "--help"], 0, "selected"),
    (["run", "selected"], 0, "worker:selected"),
    (["exec", "greet", "Ada", "--count", "2"], 0, "Hello Ada, count=2"),
    (["unknown"], 2, "No such command"),
    (["run", "unknown"], 2, "No such command"),
    (["run", "selected", "extra"], 2, "unexpected extra argument"),
    (["exec", "greet"], 2, "Missing argument"),
    (["exec", "greet", "Ada", "--count", "invalid"], 2, "Invalid value"),
    (["run", "broken"], 1, "worker failure"),
    (["run", "exit-code"], 7, "worker:exit-code"),
    (["run", "interrupt"], 130, "worker:interrupt"),
]


@pytest.mark.parametrize(("arguments", "exit_code", "message"), CASES)
def test_external_cli_preserves_application_status(arguments: list[str], exit_code: int, message: str) -> None:
    application = make_app()
    with patch("temporal_boost.cli.process_runner.import_app_object", return_value=application):
        result = CliRunner().invoke(cli_app, ["test:app", "--", *arguments])

    assert result.exit_code == exit_code, result.output
    output = result.output + str(result.exception or "")
    assert message.casefold() in output.casefold()
    assert "worker:other" not in output


@pytest.mark.parametrize("launcher", ["script", "entry_point"])
@pytest.mark.parametrize(("arguments", "exit_code", "message"), CASES)
def test_os_exit_status_matches_script_and_installed_entry_point(
    launcher: str, arguments: list[str], exit_code: int, message: str
) -> None:
    if launcher == "script":
        command = [sys.executable, str(Path(__file__).with_name("cli_exit_app.py"))]
    else:
        command = [str(Path(sys.executable).with_name("temporal-boost")), "tests.cli_exit_app:app", "--"]

    result = subprocess.run(  # noqa: S603
        [*command, *arguments],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == exit_code, output
    assert message.casefold() in output.casefold()
    assert "worker:other" not in output


def test_programmatic_argument_list_is_preserved_and_dispatches_once(capsys: pytest.CaptureFixture[str]) -> None:
    application = make_app()
    arguments = ["exec", "greet", "Ada", "--count", "2"]

    with pytest.raises(SystemExit) as raised:
        application.run(arguments)

    assert raised.value.code == 0
    assert capsys.readouterr().out.count("Hello Ada, count=2") == 1
    assert arguments == ["exec", "greet", "Ada", "--count", "2"]


def test_programmatic_empty_list_does_not_fall_back_to_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    application = make_app()
    monkeypatch.setattr(sys, "argv", ["main.py", "run", "broken"])

    with pytest.raises(SystemExit) as raised:
        application.run([])

    assert raised.value.code == 2


def test_programmatic_non_standalone_call_returns_callback_result() -> None:
    application = make_app()
    assert application.run(["exec", "greet", "Ada"], standalone_mode=False) == "Hello Ada, count=1"


def test_programmatic_non_standalone_help_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert make_app().run(["--help"], standalone_mode=False) == 0
    assert "Usage:" in capsys.readouterr().out


def test_programmatic_non_standalone_call_preserves_usage_error() -> None:
    with pytest.raises(click.UsageError, match="No such command"):
        make_app().run(["unknown"], standalone_mode=False)


def test_programmatic_non_standalone_call_preserves_worker_failure() -> None:
    with pytest.raises(RuntimeError, match="worker failure"):
        make_app().run(["run", "broken"], standalone_mode=False)


def test_programmatic_string_arguments_are_rejected() -> None:
    with pytest.raises(TypeError, match="list"):
        make_app().run("run selected")  # type: ignore[arg-type]


@pytest.mark.parametrize("exit_code", [0, None, 7])
def test_run_all_cli_cannot_report_success_after_worker_system_exit(exit_code: int | None) -> None:
    application = BoostApp(logger_config=None)
    worker = ExitCodeWorker("failed", SystemExit(exit_code))
    application.add_async_runtime(worker.name, worker)

    with patch("temporal_boost.cli.process_runner.import_app_object", return_value=application):
        result = CliRunner().invoke(cli_app, ["test:app", "run", "all"])

    assert result.exit_code == (exit_code or 1)


@pytest.mark.parametrize(("arguments", "exit_code"), [(["--help"], 0), (["--unknown"], 2)])
def test_outer_cli_retains_its_own_help_and_usage_status(arguments: list[str], exit_code: int) -> None:
    result = CliRunner().invoke(cli_app, arguments)
    assert result.exit_code == exit_code
