import logging

import typer

from temporal_boost.cli.process_runner import run_multiprocess, run_single_process


logger = logging.getLogger(__name__)
cli_app = typer.Typer(help="CLI runner for BoostApp services")


@cli_app.command("run")
def run_command(
    app: str = typer.Argument(..., help="Path to BoostApp, e.g. 'my_app.app:app'"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of processes to run"),
    arguments: list[str] = typer.Argument(None, help="Additional arguments to pass to app.run()", show_default=False),  # noqa: B008
) -> None:
    additional_arguments = arguments or []
    if workers > 1:
        logger.info(f"Starting {workers} processes for app '{app}' with arguments: {additional_arguments}")
        run_multiprocess(app, workers, additional_arguments)
    else:
        run_single_process(app, additional_arguments)
