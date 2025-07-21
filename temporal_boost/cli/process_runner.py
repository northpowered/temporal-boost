import logging
from multiprocessing import Process

from temporal_boost.cli.importer import import_app_object
from temporal_boost.cli.prometheus import setup_prometheus_multiproc_dir


logger = logging.getLogger(__name__)


def run_single_process(app_path: str, arguments: list[str]) -> None:
    application_object = import_app_object(app_path)
    try:
        application_object.run(arguments)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal in single process")
        return


def run_multiprocess(app_path: str, number_of_processes: int, arguments: list[str]) -> None:
    setup_prometheus_multiproc_dir()
    process_collection: list[Process] = []

    logger.info(f"Starting {number_of_processes} processes for app '{app_path}'")

    for index in range(number_of_processes):
        process = Process(target=run_single_process, args=(app_path, arguments), name=f"worker-{index}")
        process_collection.append(process)
        process.start()
        logger.info(f"Started process {process.name} (PID: {process.pid})")

    try:
        for process in process_collection:
            process.join()
            if process.exitcode != 0:
                logger.warning(f"Process {process.name} exited with code {process.exitcode}")
            else:
                logger.info(f"Process {process.name} completed successfully")
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, terminating child processes...")

        for process in process_collection:
            if process.is_alive():
                logger.info(f"Terminating process {process.name} (PID: {process.pid})")
                process.terminate()

        for process in process_collection:
            if process.is_alive():
                process.join(timeout=5.0)
                if process.is_alive():
                    logger.warning(f"Force killing process {process.name} (PID: {process.pid})")
                    process.kill()
                    process.join()

        logger.info("All child processes terminated")
        raise
