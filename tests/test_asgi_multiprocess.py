import os
import subprocess  # noqa: S404
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from temporal_boost import ASGIWorkerType, BaseAsgiWorker, BaseBoostWorker, BoostApp
from temporal_boost.cli.process_context import multiprocess_execution
from temporal_boost.workers.granian_worker import GranianBoostWorker
from temporal_boost.workers.hypercorn_worker import HypercornBoostWorker
from temporal_boost.workers.temporal import TemporalBoostWorker
from temporal_boost.workers.uvicorn_worker import UvicornBoostWorker


def record_run(worker: BaseBoostWorker) -> None:
    print(f"started:{worker.name}:run")  # noqa: T201 - prove CLI dispatch and detect unexpected worker startup


def record_cron(worker: TemporalBoostWorker) -> None:
    print(f"started:{worker.name}:cron")  # noqa: T201 - prove selection of the CRON command


@pytest.fixture
def mixed_app() -> Iterator[BoostApp]:
    application = BoostApp(logger_config=None)

    async def activity() -> None:
        pass

    def status(target: str = "all") -> str:
        return target

    with (
        patch.object(UvicornBoostWorker, "run", record_run),
        patch.object(TemporalBoostWorker, "run", record_run),
        patch.object(TemporalBoostWorker, "cron", record_cron),
        patch("temporal_boost.boost_app.get_asgi_worker_class", return_value=UvicornBoostWorker),
    ):
        application.add_asgi_worker("http", "example:app", "127.0.0.1", 8000)
        application.add_worker(
            "consumer", "queue", activities=[activity], cron_schedule="* * * * *", cron_runner=activity
        )
        application.add_exec_method_sync("status", status)
        yield application


@pytest.fixture(params=[False, True], ids=["plain", "color"])
def cli_runner(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    # Typer forces Rich styling on GitHub Actions, even with captured output.
    monkeypatch.setattr("typer.rich_utils.FORCE_TERMINAL", request.param)
    return CliRunner()


@pytest.mark.parametrize("arguments", [["run", "all"], ["run", "http"], ["run", "--", "http"]])
def test_replicated_asgi_command_is_rejected_before_any_worker_starts(
    mixed_app: BoostApp, arguments: list[str], cli_runner: CliRunner
) -> None:
    with multiprocess_execution(2):
        result = cli_runner.invoke(mixed_app._root_typer, arguments)

    assert result.exit_code == 2, result.output
    output = typer.unstyle(result.output)
    assert "ASGI" in output
    assert "--workers 1" in output
    assert "started:" not in output


@pytest.mark.parametrize(
    ("arguments", "exit_code"),
    [
        (["--help"], 0),
        (["run", "--help"], 0),
        (["run", "all", "--help"], 0),
        (["run", "http", "--help"], 0),
        (["run", "consumer"], 0),
        (["run", "--", "consumer"], 0),
        (["cron", "consumer"], 0),
        (["exec", "status", "--target", "all"], 0),
        (["run", "missing"], 2),
        (["cron", "http"], 2),
        (["run", "http", "unexpected"], 2),
        (["run", "all", "--unknown"], 2),
    ],
)
def test_guard_preserves_safe_commands_help_and_parser_errors(
    mixed_app: BoostApp, arguments: list[str], exit_code: int
) -> None:
    with multiprocess_execution(3):
        result = CliRunner().invoke(mixed_app._root_typer, arguments)

    assert result.exit_code == exit_code, result.output
    assert "--workers 1" not in typer.unstyle(result.output)
    assert "started:http" not in result.output
    if arguments in (["run", "consumer"], ["run", "--", "consumer"]):
        assert result.output.count("started:consumer:run") == 1
    elif arguments == ["cron", "consumer"]:
        assert result.output.count("started:consumer:cron") == 1


def test_single_process_asgi_dispatch_and_context_reset(
    mixed_app: BoostApp, capsys: pytest.CaptureFixture[str]
) -> None:
    with multiprocess_execution(2), multiprocess_execution(1):
        mixed_app.run(["run", "http"], standalone_mode=False)
    mixed_app.run(["run", "http"], standalone_mode=False)
    assert capsys.readouterr().out.count("started:http:run") == 2


def test_single_process_run_all_is_allowed(mixed_app: BoostApp) -> None:
    with multiprocess_execution(1), patch.object(mixed_app, "run_all_workers") as run_all:
        result = CliRunner().invoke(mixed_app._root_typer, ["run", "all"])
    assert result.exit_code == 0, result.output
    run_all.assert_called_once_with()


def test_failed_multiprocess_dispatch_does_not_restrict_later_invocations(mixed_app: BoostApp) -> None:
    with multiprocess_execution(2):
        with pytest.raises(typer.BadParameter, match="ASGI"):
            mixed_app.run(["run", "http"], standalone_mode=False)
    assert CliRunner().invoke(mixed_app._root_typer, ["run", "http"]).exit_code == 0


@pytest.mark.parametrize(
    ("backend", "worker_class"),
    [
        (ASGIWorkerType.uvicorn, UvicornBoostWorker),
        (ASGIWorkerType.hypercorn, HypercornBoostWorker),
        (ASGIWorkerType.granian, GranianBoostWorker),
    ],
)
def test_all_backends_are_guarded(backend: ASGIWorkerType, worker_class: type[BaseAsgiWorker]) -> None:
    application = BoostApp(logger_config=None)
    with (
        patch("temporal_boost.boost_app.get_asgi_worker_class", return_value=worker_class),
        patch.object(worker_class, "run", record_run),
    ):
        application.add_asgi_worker("http", "example:app", "127.0.0.1", 8000, asgi_worker_type=backend)
        with multiprocess_execution(2):
            result = CliRunner().invoke(application._root_typer, ["run", "http"])
    assert result.exit_code == 2, result.output
    assert "started:" not in result.output


def test_custom_asgi_registered_as_runtime_is_guarded() -> None:
    application = BoostApp(logger_config=None)
    with patch.object(UvicornBoostWorker, "run", record_run):
        worker = UvicornBoostWorker("example:app", "127.0.0.1", 8000)
        worker.name = "custom_http"
        application.add_async_runtime(worker.name, worker)
        with multiprocess_execution(2):
            result = CliRunner().invoke(application._root_typer, ["run", "custom_http"])
    assert result.exit_code == 2, result.output
    assert "started:" not in result.output


def test_custom_asgi_command_keeps_its_cli_parameters(cli_runner: CliRunner) -> None:
    class CustomWorker(BaseAsgiWorker):
        def run(self, label: str = "default") -> None:
            print(f"http:{label}")  # noqa: T201 - observe actual callback arguments

    application = BoostApp(logger_config=None)
    worker = CustomWorker("unused:app", "127.0.0.1", 8000)
    worker.name = "http"
    application.add_async_runtime(worker.name, worker)

    result = cli_runner.invoke(application._root_typer, ["run", "http", "--label", "selected"])
    assert result.exit_code == 0, result.output
    assert "http:selected" in result.output
    with multiprocess_execution(2):
        result = cli_runner.invoke(application._root_typer, ["run", "http", "--label", "selected"])
    assert result.exit_code == 2, result.output
    output = typer.unstyle(result.output)
    assert "--workers 1" in output
    assert "http:selected" not in output


def launch_cli(arguments: list[str], workers: int, directory: Path, port: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [
            str(Path(sys.executable).with_name("temporal-boost")),
            "--workers",
            str(workers),
            "--shutdown-timeout",
            "0.5",
            "tests.asgi_multiprocess_app:app",
            "--",
            *arguments,
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={
            **os.environ,
            "ASGI_TEST_RESULTS": str(directory),
            "ASGI_TEST_PORT": str(port),
            "PROMETHEUS_MULTIPROC_DIR": str(directory),
        },
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


@pytest.mark.parametrize("arguments", [["run", "all"], ["run", "http"]])
@pytest.mark.integration
def test_real_two_process_asgi_launch_fails_before_any_bind(
    tmp_path: Path, unused_tcp_port: int, arguments: list[str]
) -> None:
    result = launch_cli(arguments, 2, tmp_path, unused_tcp_port)
    output = typer.unstyle(result.stdout + result.stderr)
    assert result.returncode == 2, output
    assert "ASGI" in output
    assert "--workers 1" in output
    assert "Address already in use" not in output
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("arguments", "role"),
    [
        (["run", "consumer"], "consumer"),
        (["cron", "consumer"], "cron"),
        (["exec", "mark", "--target", "all"], "exec-all"),
    ],
)
@pytest.mark.integration
def test_real_two_process_safe_selection_does_not_start_registered_http(
    tmp_path: Path, unused_tcp_port: int, arguments: list[str], role: str
) -> None:
    result = launch_cli(arguments, 2, tmp_path, unused_tcp_port)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(list(tmp_path.glob(f"{role}.*"))) == 2
    assert len(list(tmp_path.iterdir())) == 2


@pytest.mark.integration
def test_real_replicated_http_help_is_allowed(tmp_path: Path, unused_tcp_port: int) -> None:
    result = launch_cli(["run", "http", "--help"], 2, tmp_path, unused_tcp_port)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Usage:" in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.integration
def test_real_single_process_http_can_bind_temporary_port(tmp_path: Path, unused_tcp_port: int) -> None:
    result = launch_cli(["run", "http"], 1, tmp_path, unused_tcp_port)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(list(tmp_path.glob("http-bound.*"))) == 1
    assert len(list(tmp_path.iterdir())) == 2
