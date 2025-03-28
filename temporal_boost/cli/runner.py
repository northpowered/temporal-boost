import importlib
import logging
import os
import tempfile
from multiprocessing import Process
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer


if TYPE_CHECKING:
    from types import ModuleType


logger = logging.getLogger(__name__)
cli = typer.Typer(help="CLI runner for BoostApp services")


def setup_prometheus_multiproc_dir() -> None:
    prometheus_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")

    if prometheus_dir:
        path = Path(prometheus_dir)
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created prometheus multiprocess dir at {prometheus_dir}")
            except Exception as e:
                logger.warning(f"Cannot create prometheus multiprocess dir '{prometheus_dir}': {e}")
                del os.environ["PROMETHEUS_MULTIPROC_DIR"]
                logger.warning("Unset PROMETHEUS_MULTIPROC_DIR due to errors")
    else:
        try:
            temp_dir = tempfile.mkdtemp(prefix="prometheus_multiproc_")
            os.environ["PROMETHEUS_MULTIPROC_DIR"] = temp_dir
            logger.info(f"Set temporary PROMETHEUS_MULTIPROC_DIR at {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to set temporary PROMETHEUS_MULTIPROC_DIR: {e}")


def _import_app_object(app_path: str) -> Any:
    if ":" not in app_path:
        raise typer.BadParameter("App path must be in format 'module.submodule:app'")
    module_path, app_attr = app_path.split(":")
    module: ModuleType = importlib.import_module(module_path)
    app = getattr(module, app_attr, None)
    if app is None:
        raise typer.BadParameter(f"No '{app_attr}' found in module '{module_path}'")
    return app


def _run_single(app_path: str, run_args: list[str]) -> None:
    app = _import_app_object(app_path)
    app.run(run_args)


def _run_multiprocess(app_path: str, processes: int, run_args: list[str]) -> None:
    setup_prometheus_multiproc_dir()

    process_list: list[Process] = []
    for index in range(processes):
        process = Process(target=_run_single, args=(app_path, run_args), name=f"worker-{index}")
        process_list.append(process)
        process.start()

    for process in process_list:
        process.join()


@cli.command("run")
def run(
    app: str = typer.Argument(..., help="Path to BoostApp, e.g. 'my_app.app:app'"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of processes to run"),
    run_args: list[str] = typer.Argument(None, help="Additional arguments to pass to app.run()", show_default=False),  # noqa: B008
) -> None:
    additional_args = run_args or []
    if workers > 1:
        logger.info(f"Starting {workers} processes for app '{app}' with arguments: {additional_args}")
        _run_multiprocess(app, workers, additional_args)
    else:
        _run_single(app, additional_args)


if __name__ == "__main__":
    cli()
