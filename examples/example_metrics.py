"""Two worker-owned exporters; scrape both endpoints in every process.

Start a local Temporal server first, then run in separate terminals:
  METRICS_BASE_PORT=9100 uv run python examples/example_metrics.py run all
  METRICS_BASE_PORT=9102 uv run python examples/example_metrics.py run all

Scrape /metrics on ports 9100, 9101, 9102, and 9103. METRICS_BASE_PORT is
owned by this example, not a framework environment setting. External --workers
would repeat the same ports; use separate processes with distinct base ports.
"""

import os
from datetime import timedelta

from temporalio import activity, workflow

from temporal_boost import BoostApp


@activity.defn
async def echo(message: str) -> str:
    return message


@workflow.defn(sandboxed=False)
class EchoWorkflow:
    @workflow.run
    async def run(self, message: str) -> str:
        return await workflow.execute_activity(echo, message, start_to_close_timeout=timedelta(seconds=10))


app = BoostApp(name="metrics-example")
base_port = int(os.environ.get("METRICS_BASE_PORT", "9100"))
for offset, name in enumerate(("payments", "notifications")):
    worker = app.add_worker(name, f"{name}-queue", activities=[echo], workflows=[EchoWorkflow])
    worker.configure_temporal_runtime(
        prometheus_bind_address=f"0.0.0.0:{base_port + offset}",
        prometheus_counters_total_suffix=True,
        global_tags={"boost_worker": name},
    )

if __name__ == "__main__":
    app.run()
