from multiprocessing import Process

from temporal_boost.cli.importer import import_app_object
from temporal_boost.cli.prometheus import setup_prometheus_multiproc_dir


def run_single_process(app_path: str, arguments: list[str]) -> None:
    application_object = import_app_object(app_path)
    application_object.run(arguments)


def run_multiprocess(app_path: str, number_of_processes: int, arguments: list[str]) -> None:
    setup_prometheus_multiproc_dir()
    process_collection: list[Process] = []
    for index in range(number_of_processes):
        process = Process(target=run_single_process, args=(app_path, arguments), name=f"worker-{index}")
        process_collection.append(process)
        process.start()
    for process in process_collection:
        process.join()
