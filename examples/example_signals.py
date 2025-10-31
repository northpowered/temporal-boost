"""
Workflow with signals example for Temporal-boost.

This example demonstrates:
- Workflows that wait for external signals
- Signal handlers
- Approval workflows

Run with: python3 example_signals.py run approval_worker
Then send signals using the client script.
"""

import logging
from temporalio import workflow
from temporal_boost import BoostApp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BoostApp(name="signals-example")

@workflow.defn(sandboxed=False, name="ApprovalWorkflow")
class ApprovalWorkflow:
    """Workflow that waits for approval/rejection signals."""
    
    def __init__(self):
        self.approved = False
        self.rejected = False
        self.comments = ""
        self.request_id = ""

    @workflow.run
    async def run(self, request_id: str) -> dict:
        """Wait for approval signal."""
        self.request_id = request_id
        logger.info(f"Approval workflow started for request: {request_id}")
        
        # Wait until we receive an approval or rejection signal
        await workflow.wait_condition(lambda: self.approved or self.rejected)
        
        if self.approved:
            logger.info(f"Request {request_id} was approved")
            return {
                "status": "approved",
                "request_id": request_id,
                "comments": self.comments,
            }
        
        logger.info(f"Request {request_id} was rejected")
        return {
            "status": "rejected",
            "request_id": request_id,
            "comments": self.comments,
        }

    @workflow.signal(name="approve")
    def approve(self, comments: str = "") -> None:
        """Signal handler for approval."""
        logger.info(f"Received approval signal for {self.request_id}")
        self.approved = True
        self.comments = comments

    @workflow.signal(name="reject")
    def reject(self, comments: str) -> None:
        """Signal handler for rejection."""
        logger.info(f"Received rejection signal for {self.request_id}")
        self.rejected = True
        self.comments = comments

app.add_worker("approval_worker", "approval_queue", workflows=[ApprovalWorkflow])

if __name__ == "__main__":
    app.run()

