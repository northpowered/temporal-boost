import logging
import multiprocessing
import os
import tempfile
from pathlib import Path


logger = logging.getLogger(__name__)


def setup_prometheus_multiproc_dir() -> None:
    process_id = multiprocessing.current_process().name
    logger.info(f"Setting up Prometheus multiprocess directory for process: {process_id}")

    prometheus_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")
    if prometheus_dir:
        directory_path = Path(prometheus_dir)
        if not directory_path.exists():
            try:
                directory_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Process {process_id}: Created Prometheus multiprocess directory at {prometheus_dir}")
            except Exception as exception_detail:
                logger.warning(
                    f"Process {process_id}: Cannot create Prometheus multiprocess directory "
                    f"'{prometheus_dir}': {exception_detail}",
                )
                del os.environ["PROMETHEUS_MULTIPROC_DIR"]
                logger.warning(f"Process {process_id}: Unset PROMETHEUS_MULTIPROC_DIR due to errors")
    else:
        try:
            temporary_directory = tempfile.mkdtemp(prefix="prometheus_multiproc_")
            os.environ["PROMETHEUS_MULTIPROC_DIR"] = temporary_directory
            logger.info(f"Process {process_id}: Set temporary PROMETHEUS_MULTIPROC_DIR at {temporary_directory}")
        except Exception as exception_detail:
            logger.warning(
                f"Process {process_id}: Failed to set temporary PROMETHEUS_MULTIPROC_DIR: {exception_detail}",
            )
