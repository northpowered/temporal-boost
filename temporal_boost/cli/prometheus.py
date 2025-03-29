import logging
import os
import tempfile
from pathlib import Path


logger = logging.getLogger(__name__)


def setup_prometheus_multiproc_dir() -> None:
    prometheus_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")
    if prometheus_dir:
        directory_path = Path(prometheus_dir)
        if not directory_path.exists():
            try:
                directory_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created Prometheus multiprocess directory at {prometheus_dir}")
            except Exception as exception_detail:
                logger.warning(
                    f"Cannot create Prometheus multiprocess directory '{prometheus_dir}': {exception_detail}"
                )
                del os.environ["PROMETHEUS_MULTIPROC_DIR"]
                logger.warning("Unset PROMETHEUS_MULTIPROC_DIR due to errors")
    else:
        try:
            temporary_directory = tempfile.mkdtemp(prefix="prometheus_multiproc_")
            os.environ["PROMETHEUS_MULTIPROC_DIR"] = temporary_directory
            logger.info(f"Set temporary PROMETHEUS_MULTIPROC_DIR at {temporary_directory}")
        except Exception as exception_detail:
            logger.warning(f"Failed to set temporary PROMETHEUS_MULTIPROC_DIR: {exception_detail}")
