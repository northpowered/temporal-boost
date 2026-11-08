"""Real SDK exporter fixture; optional worker mode consumes an ephemeral Temporal server."""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from temporalio import activity, workflow

from temporal_boost import BoostApp
from temporal_boost.workers.temporal import TemporalBoostWorker


@activity.defn(name="metrics_probe")
async def metrics_probe() -> str:
    activity.metric_meter().create_counter("boost_metrics_probe").add(1)
    return activity.info().task_queue


@workflow.defn(name="MetricsProbe", sandboxed=False)
class MetricsProbe:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(metrics_probe, start_to_close_timeout=timedelta(seconds=10))


def emit_probe(worker: TemporalBoostWorker, value: int) -> None:
    worker.temporal_client_runtime.metric_meter.create_counter("boost_metrics_probe").add(value)


def main() -> None:
    mode, port_list, ready_path, target = sys.argv[1:]
    ports = [int(port) for port in port_list.split(",")]
    app = BoostApp(logger_config=None, temporal_endpoint=target, shutdown_timeout=5)
    workers = []
    for index, port in enumerate(ports):
        worker = app.add_worker(
            f"worker-{index}", f"metrics-{os.getpid()}-{index}", activities=[metrics_probe], workflows=[MetricsProbe]
        )
        worker.configure_temporal_runtime(
            prometheus_bind_address=f"127.0.0.1:{port}",
            prometheus_counters_total_suffix=True,
            global_tags={"boost_worker": worker.name, "process_id": str(os.getpid())},
        )
        workers.append(worker)

    if mode == "meter":
        # Two independent worker-owned SDK runtimes on different Python threads.
        with ThreadPoolExecutor(max_workers=len(workers)) as executor:
            list(executor.map(emit_probe, workers, range(1, len(workers) + 1)))
    Path(ready_path).write_text(
        json.dumps({"pid": os.getpid(), "queues": [worker._worker_builder.task_queue for worker in workers]}),
        encoding="utf-8",
    )
    if mode == "meter":
        sys.stdin.readline()
    else:
        app.run_all_workers()


if __name__ == "__main__":
    main()
