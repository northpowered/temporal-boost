from __future__ import annotations

import os
import signal
import subprocess  # noqa: S404
import sys
import threading
import time
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from temporal_boost.cli import process_runner
from temporal_boost.cli.runner import cli_app


if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


class ProcessDouble:
    def __init__(self, exit_code: int | None = None, *, cooperative: bool = True) -> None:
        self.name = ""
        self.pid: int | None = None
        self.exitcode: int | None = None
        self.initial_exit_code = exit_code
        self.cooperative = cooperative
        self.ignore_terminate = False
        self.start_error: BaseException | None = None
        self.terminate_error: BaseException | None = None
        self.after_start: Callable[[], None] | None = None
        self.closed = False
        self.joins = 0
        self.terminated_at: float | None = None
        self.killed_at: float | None = None
        self.clock: Callable[[], float] = lambda: 0

    def start(self) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.pid = 100
        self.exitcode = self.initial_exit_code
        if self.after_start is not None:
            self.after_start()

    def join(self, timeout: float | None = None) -> None:
        assert timeout is not None, "Supervisor must not block on one child"
        assert self.pid is not None, "Cannot join an unstarted process"
        self.joins += 1

    def is_alive(self) -> bool:
        return self.pid is not None and self.exitcode is None

    def terminate(self) -> None:
        self.terminated_at = self.clock()
        if self.terminate_error is not None:
            raise self.terminate_error
        if not self.ignore_terminate:
            self.exitcode = -signal.SIGTERM

    def kill(self) -> None:
        self.killed_at = self.clock()
        self.exitcode = -signal.SIGKILL

    def close(self) -> None:
        assert not self.is_alive(), "Cannot close a live process"
        self.closed = True


class Harness:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, processes: list[ProcessDouble]) -> None:
        self.processes = processes
        self.created: list[ProcessDouble] = []
        self.stop = threading.Event()
        self.now = 0.0
        self.handlers: dict[int, Any] = {signal.SIGINT: signal.SIG_DFL, signal.SIGTERM: signal.SIG_DFL}
        self.tick_action: Callable[[], None] | None = None
        self.pipes: list[tuple[MagicMock, MagicMock]] = []
        monkeypatch.setattr(process_runner, "Process", self.make_process)
        monkeypatch.setattr(process_runner, "Pipe", self.make_pipe)
        monkeypatch.setattr(process_runner, "TERMINATE_TIMEOUT", 0.2, raising=False)
        monkeypatch.setattr(process_runner, "KILL_TIMEOUT", 0.2, raising=False)
        monkeypatch.setattr(process_runner, "time", time, raising=False)
        monkeypatch.setattr(process_runner, "signal", signal, raising=False)
        monkeypatch.setattr(process_runner.time, "monotonic", lambda: self.now)
        monkeypatch.setattr(process_runner.time, "sleep", self.tick)
        monkeypatch.setattr(process_runner.signal, "signal", self.set_handler)

    def make_process(self, *, target: Any, args: tuple[Any, ...], name: str) -> ProcessDouble:
        assert callable(target)
        assert args[:2] == ("test:app", ["run", "all"])
        process = self.processes[len(self.created)]
        process.name = name
        process.clock = lambda: self.now
        self.created.append(process)
        return process

    def make_pipe(self, *, duplex: bool) -> tuple[MagicMock, MagicMock]:
        assert not duplex
        reader, writer = MagicMock(), MagicMock()
        writer.send_bytes.side_effect = lambda _message: self.stop.set()
        self.pipes.append((reader, writer))
        return reader, writer

    def set_handler(self, signum: int, handler: Any) -> Any:
        previous = self.handlers[signum]
        self.handlers[signum] = handler
        return previous

    def signal(self, signum: int) -> None:
        self.handlers[signum](signum, None)

    def tick(self, delay: float) -> None:
        self.now += delay
        if self.tick_action is not None:
            self.tick_action()
        if self.stop.is_set():
            for process in self.created:
                if process.cooperative and process.is_alive():
                    process.exitcode = 0

    def run(self, shutdown_timeout: float | None = None) -> None:
        if shutdown_timeout is None:
            process_runner.run_multiprocess("test:app", len(self.processes), ["run", "all"])
        else:
            process_runner.run_multiprocess(
                "test:app", len(self.processes), ["run", "all"], shutdown_timeout=shutdown_timeout
            )

    def assert_clean(self) -> None:
        assert all(process.closed for process in self.created)
        assert all(process.joins > 0 for process in self.created if process.pid is not None)
        assert self.handlers == {signal.SIGINT: signal.SIG_DFL, signal.SIGTERM: signal.SIG_DFL}
        for reader, writer in self.pipes:
            reader.close.assert_called_once()
            writer.close.assert_called_once()


@pytest.mark.parametrize("exit_code", [1, 7, -signal.SIGTERM])
def test_later_child_failure_stops_live_first_child_and_preserves_status(
    monkeypatch: pytest.MonkeyPatch, exit_code: int
) -> None:
    first, second = ProcessDouble(), ProcessDouble(exit_code)
    harness = Harness(monkeypatch, [first, second])

    with pytest.raises(SystemExit) as raised:
        harness.run()

    assert raised.value.code == (exit_code if exit_code > 0 else 128 - exit_code)
    assert harness.stop.is_set()
    assert first.exitcode == 0
    assert first.terminated_at is None
    harness.assert_clean()


@pytest.mark.parametrize("failure", [RuntimeError("second start failed"), KeyboardInterrupt()])
def test_partial_start_failure_cleans_started_child_and_preserves_error(
    monkeypatch: pytest.MonkeyPatch, failure: BaseException
) -> None:
    first, second = ProcessDouble(), ProcessDouble()
    second.start_error = failure
    harness = Harness(monkeypatch, [first, second])

    with pytest.raises(type(failure)) as raised:
        harness.run()

    assert raised.value is failure
    assert first.exitcode == 0
    assert second.joins == 0
    harness.assert_clean()


def test_successful_finite_children_are_joined_and_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = Harness(monkeypatch, [ProcessDouble(0), ProcessDouble(0)])
    harness.run()
    harness.assert_clean()


def test_start_failure_after_pid_assignment_stops_both_children(monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = ProcessDouble(), ProcessDouble()
    failure = RuntimeError("start failed after launch")

    def fail() -> None:
        raise failure

    second.after_start = fail
    harness = Harness(monkeypatch, [first, second])
    with pytest.raises(RuntimeError) as raised:
        harness.run()
    assert raised.value is failure
    assert first.exitcode == second.exitcode == 0
    harness.assert_clean()


def test_start_failure_with_success_system_exit_cannot_report_success(monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = ProcessDouble(), ProcessDouble()
    failure = SystemExit(0)
    second.start_error = failure
    harness = Harness(monkeypatch, [first, second])
    with pytest.raises(RuntimeError, match="success exit code") as raised:
        harness.run()
    assert raised.value.__cause__ is failure
    harness.assert_clean()


def test_one_terminate_failure_does_not_skip_other_children(monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = ProcessDouble(cooperative=False), ProcessDouble(cooperative=False)
    failure = ValueError("terminate failed")
    first.terminate_error = failure
    harness = Harness(monkeypatch, [first, second])
    second.after_start = lambda: harness.signal(signal.SIGTERM)

    with pytest.raises(ValueError, match="terminate failed") as raised:
        harness.run(shutdown_timeout=0)

    assert raised.value is failure
    assert second.terminated_at is not None
    assert first.killed_at is not None
    harness.assert_clean()


@pytest.mark.parametrize("operation", ["send_bytes", "close"])
def test_stop_pipe_failure_does_not_skip_other_children(monkeypatch: pytest.MonkeyPatch, operation: str) -> None:
    first, second = ProcessDouble(), ProcessDouble()
    harness = Harness(monkeypatch, [first, second])
    failure = OSError("stop pipe failed")

    def request_shutdown() -> None:
        getattr(harness.pipes[0][1], operation).side_effect = failure
        harness.signal(signal.SIGTERM)

    second.after_start = request_shutdown
    with pytest.raises(OSError, match="stop pipe failed") as raised:
        harness.run()

    assert raised.value is failure
    harness.pipes[1][1].send_bytes.assert_called_once_with(b"stop")
    assert first.terminated_at is second.terminated_at is None
    harness.assert_clean()


def test_already_closed_child_pipe_does_not_fail_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = ProcessDouble(), ProcessDouble()
    harness = Harness(monkeypatch, [first, second])

    def request_shutdown() -> None:
        harness.pipes[0][1].send_bytes.side_effect = BrokenPipeError("child exited")
        harness.signal(signal.SIGTERM)

    second.after_start = request_shutdown
    with pytest.raises(SystemExit) as raised:
        harness.run()

    assert raised.value.code == 128 + signal.SIGTERM
    harness.assert_clean()


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_parent_signal_and_repeats_request_cooperative_stop_and_restore_handlers(
    monkeypatch: pytest.MonkeyPatch, signum: int
) -> None:
    first, second = ProcessDouble(), ProcessDouble()
    harness = Harness(monkeypatch, [first, second])
    second.after_start = lambda: harness.signal(signum)
    harness.tick_action = lambda: harness.signal(signum)

    with pytest.raises(SystemExit) as raised:
        harness.run()

    assert raised.value.code == 128 + signum
    assert first.terminated_at is second.terminated_at is None
    harness.assert_clean()


def test_all_children_share_grace_and_escalation_deadlines(monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = ProcessDouble(cooperative=False), ProcessDouble(cooperative=False)
    first.ignore_terminate = second.ignore_terminate = True
    harness = Harness(monkeypatch, [first, second])
    second.after_start = lambda: harness.signal(signal.SIGTERM)

    with pytest.raises(SystemExit) as raised:
        harness.run(shutdown_timeout=0.3)

    assert raised.value.code == 128 + signal.SIGTERM
    assert first.terminated_at == pytest.approx(0.3)
    assert second.terminated_at == pytest.approx(0.3)
    assert first.killed_at == pytest.approx(0.5)
    assert second.killed_at == pytest.approx(0.5)
    assert harness.now < 0.8
    harness.assert_clean()


def test_cleanup_error_does_not_replace_child_failure_or_skip_kill(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    first, second = ProcessDouble(cooperative=False), ProcessDouble(7)
    first.terminate_error = ValueError("terminate failed")
    harness = Harness(monkeypatch, [first, second])

    with pytest.raises(SystemExit) as raised:
        harness.run(shutdown_timeout=0)

    assert raised.value.code == 7
    assert first.killed_at is not None
    assert "terminate failed" in caplog.text
    logged_error = next(
        record.exc_info for record in caplog.records if record.exc_info and record.exc_info[1] is first.terminate_error
    )
    assert logged_error is not None
    assert logged_error[2] is not None
    harness.assert_clean()


def test_join_error_does_not_replace_observed_child_failure_or_skip_close(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    first, second = ProcessDouble(), ProcessDouble(7)
    harness = Harness(monkeypatch, [first, second])
    with patch.object(second, "join", side_effect=ValueError("join failed")):
        with pytest.raises(SystemExit) as raised:
            harness.run()
    assert raised.value.code == 7
    assert second.closed
    assert "join failed" in caplog.text
    assert first.closed


def test_observed_stop_prevents_starting_remaining_children(monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = ProcessDouble(7), ProcessDouble()
    harness = Harness(monkeypatch, [first, second])

    with pytest.raises(SystemExit):
        harness.run()

    assert harness.created == [first]
    harness.assert_clean()


@pytest.mark.parametrize("timeout", [-1, float("nan"), float("inf")])
def test_invalid_grace_is_rejected_before_starting(monkeypatch: pytest.MonkeyPatch, timeout: float) -> None:
    harness = Harness(monkeypatch, [ProcessDouble()])
    with pytest.raises(ValueError, match="shutdown_timeout"):
        harness.run(timeout)
    assert harness.created == []


@pytest.mark.parametrize("count", [0, -1])
def test_invalid_process_count_is_rejected_before_starting(monkeypatch: pytest.MonkeyPatch, count: int) -> None:
    harness = Harness(monkeypatch, [ProcessDouble()])
    with pytest.raises(ValueError, match="number_of_processes"):
        process_runner.run_multiprocess("test:app", count, ["run", "all"])
    assert harness.created == []


@pytest.mark.parametrize("workers", [1, 2])
def test_cli_selects_process_mode_and_forwards_grace_period(workers: int) -> None:
    with (
        patch("temporal_boost.cli.runner.run_multiprocess") as multiple,
        patch("temporal_boost.cli.runner.run_single_process") as single,
    ):
        result = CliRunner().invoke(
            cli_app, ["--workers", str(workers), "--shutdown-timeout", "1.5", "test:app", "run", "all"]
        )
    assert result.exit_code == 0, result.exception
    if workers == 1:
        single.assert_called_once_with("test:app", ["run", "all"])
        multiple.assert_not_called()
    else:
        multiple.assert_called_once_with("test:app", 2, ["run", "all"], shutdown_timeout=1.5)
        single.assert_not_called()


@pytest.mark.parametrize("timeout", ["-1", "nan", "inf"])
def test_cli_rejects_invalid_shutdown_timeout_before_launch(timeout: str) -> None:
    with patch("temporal_boost.cli.runner.run_multiprocess") as multiple:
        result = CliRunner().invoke(
            cli_app, ["--workers", "2", "--shutdown-timeout", timeout, "test:app", "run", "all"]
        )
    assert result.exit_code == 2
    multiple.assert_not_called()


@pytest.mark.parametrize("command", ["run", "cron"])
def test_child_stop_watcher_requests_only_selected_worker_stop(command: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_runner, "POLL_INTERVAL", 0.001)
    stop, finished = MagicMock(), threading.Event()
    stop.poll.return_value = True
    application, selected, other = MagicMock(), MagicMock(), MagicMock()
    selected.name, other.name = "selected", "other"
    application.get_registered_workers.return_value = [other, selected]
    selected.request_stop.side_effect = finished.set

    process_runner._watch_for_stop(application, [command, "selected"], stop, finished)

    selected.request_stop.assert_called_once()
    other.request_stop.assert_not_called()


def test_child_stop_watcher_retries_application_stop_during_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_runner, "POLL_INTERVAL", 0.001)
    stop, finished = MagicMock(), threading.Event()
    stop.poll.return_value = True
    application = MagicMock()

    def request_stop() -> None:
        if application.stop.call_count == 2:
            finished.set()

    application.stop.side_effect = request_stop
    process_runner._watch_for_stop(application, ["run", "all"], stop, finished)
    assert application.stop.call_count == 2
    application.get_registered_workers.assert_not_called()


def test_child_stop_callback_failure_is_logged_without_unhandled_thread_exception(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(process_runner, "POLL_INTERVAL", 0.001)
    stop, finished = MagicMock(), threading.Event()
    stop.poll.return_value = True
    application = MagicMock()
    application.stop.side_effect = RuntimeError("stop callback failed")
    process_runner._watch_for_stop(application, ["run", "all"], stop, finished)
    assert "stop callback failed" in caplog.text


def test_stop_before_child_import_skips_application(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = MagicMock()
    stop.poll.return_value = True
    monkeypatch.setattr(process_runner.signal, "signal", MagicMock())
    with patch.object(process_runner, "import_app_object") as import_app:
        process_runner._run_child_process("test:app", ["run", "all"], stop)
    import_app.assert_not_called()


def test_stop_during_child_import_skips_cli_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = MagicMock()
    stop.poll.side_effect = [False, True]
    application = MagicMock()
    monkeypatch.setattr(process_runner.signal, "signal", MagicMock())

    def import_app(_path: str) -> MagicMock:
        return application

    with patch.object(process_runner, "import_app_object", side_effect=import_app):
        process_runner._run_child_process("test:app", ["run", "all"], stop)
    application.run.assert_not_called()


@contextmanager
def launched(command: list[str], directory: Path) -> Iterator[subprocess.Popen[str]]:
    environment = {**os.environ, "PROMETHEUS_MULTIPROC_DIR": str(directory)}
    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        yield process
    finally:
        # Each fixture owns a new session; failed assertions cannot orphan children.
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate(timeout=5)


def fixture_command(mode: str, directory: Path, worker: str = "all") -> list[str]:
    return [
        sys.executable,
        "-u",
        str(Path(__file__).with_name("process_supervision_app.py")),
        mode,
        str(directory),
        worker,
    ]


def wait_for_files(process: subprocess.Popen[str], files: list[Path]) -> None:
    deadline = time.monotonic() + 8
    while not all(path.exists() for path in files):
        assert time.monotonic() < deadline, f"Timed out waiting for {files}"
        if process.poll() is not None:
            pytest.fail(f"Supervisor exited early: {process.communicate(timeout=1)}")
        time.sleep(0.01)


def assert_children_reaped(directory: Path) -> None:
    assert (directory / "reaped").read_text() == "handlers restored; no children"
    for path in directory.glob("*.ready"):
        with pytest.raises(ProcessLookupError):
            os.kill(int(path.read_text()), 0)


@pytest.mark.skipif(os.name != "posix", reason="POSIX signal and process-session integration")
def test_real_later_child_failure_stops_first_and_reaps_every_child(tmp_path: Path) -> None:
    (tmp_path / "release").touch()
    with launched(fixture_command("fail-second", tmp_path), tmp_path) as process:
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 1, (stdout, stderr)
        assert "second child failed while first was running" in stderr
        assert (tmp_path / "worker-0.cleanup").exists()
        assert (tmp_path / "worker-0.returned").exists()
        assert_children_reaped(tmp_path)


@pytest.mark.skipif(os.name != "posix", reason="POSIX signal and process-session integration")
def test_real_second_start_failure_cleans_started_child(tmp_path: Path) -> None:
    (tmp_path / "release").touch()
    with launched(fixture_command("start-failure", tmp_path), tmp_path) as process:
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 1, (stdout, stderr)
        assert "injected second start failure" in stderr
        assert (tmp_path / "worker-0.returned").exists()
        assert not (tmp_path / "worker-1.ready").exists()
        assert_children_reaped(tmp_path)


@pytest.mark.skipif(os.name != "posix", reason="POSIX signal and process-session integration")
@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("worker", ["all", "service"])
def test_real_parent_signal_stops_workers_cooperatively_and_restores_handlers(
    tmp_path: Path, signum: int, worker: str
) -> None:
    with launched(fixture_command("cooperative", tmp_path, worker), tmp_path) as process:
        wait_for_files(process, [tmp_path / f"worker-{index}.ready" for index in range(2)])
        process.send_signal(signum)
        wait_for_files(process, [tmp_path / f"worker-{index}.cleanup" for index in range(2)])
        process.send_signal(signum)
        (tmp_path / "release").touch()
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 128 + signum, (stdout, stderr)
        assert "Escalating" not in stderr
        assert all((tmp_path / f"worker-{index}.returned").exists() for index in range(2))
        assert_children_reaped(tmp_path)


@pytest.mark.skipif(os.name != "posix", reason="POSIX signal and process-session integration")
def test_real_uncooperative_workers_are_killed_after_grace(tmp_path: Path) -> None:
    with launched(fixture_command("stubborn", tmp_path, "service"), tmp_path) as process:
        wait_for_files(process, [tmp_path / f"worker-{index}.ready" for index in range(2)])
        started = time.monotonic()
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=10)
        elapsed = time.monotonic() - started
        assert process.returncode == 128 + signal.SIGTERM, (stdout, stderr)
        assert elapsed >= 0.3
        assert "terminate worker-0" in stderr
        assert "kill worker-1" in stderr
        assert_children_reaped(tmp_path)


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-session cleanup")
@pytest.mark.parametrize(
    ("arguments", "exit_code"),
    [(["run", "selected"], 0), (["unknown"], 2), (["run", "broken"], 1), (["run", "exit-code"], 7)],
)
def test_installed_cli_aggregates_real_child_exit_codes(tmp_path: Path, arguments: list[str], exit_code: int) -> None:
    command = [
        str(Path(sys.executable).with_name("temporal-boost")),
        "--workers",
        "2",
        "--shutdown-timeout",
        "0.5",
        "tests.cli_exit_app:app",
        "--",
        *arguments,
    ]
    with launched(command, tmp_path) as process:
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == exit_code, (stdout, stderr)


@pytest.mark.parametrize("configured_path", ["unset", "directory", "file", "missing"])
@pytest.mark.parametrize("start_fails", [False, True])
def test_repeated_process_runs_do_not_manage_prometheus_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, configured_path: str, start_fails: bool
) -> None:
    directory = tmp_path / "user-metrics"
    directory.mkdir()
    data = directory / "owned-by-user.db"
    data.write_text("keep")
    file_path = tmp_path / "plain-file"
    file_path.write_text("keep-file")
    missing = tmp_path / "not-created"
    paths = {"directory": directory, "file": file_path, "missing": missing}
    if configured_path == "unset":
        monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    else:
        monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(paths[configured_path]))
    before_environment = dict(os.environ)
    before_files = sorted(tmp_path.rglob("*"))
    with patch("tempfile.mkdtemp", side_effect=AssertionError("No managed Prometheus directories")):
        for _ in range(2):
            children = [ProcessDouble(0), ProcessDouble(0)]
            failure = RuntimeError("process could not start")
            if start_fails:
                children[1].start_error = failure
            harness = Harness(monkeypatch, children)
            if start_fails:
                with pytest.raises(RuntimeError) as raised:
                    harness.run()
                assert raised.value is failure
            else:
                harness.run()
            harness.assert_clean()
    assert dict(os.environ) == before_environment
    assert sorted(tmp_path.rglob("*")) == before_files
    assert data.read_text() == "keep"
    assert file_path.read_text() == "keep-file"
    assert not missing.exists()
