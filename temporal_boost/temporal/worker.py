from collections.abc import Callable
from datetime import timedelta
from math import isfinite
from typing import Any

from temporalio.client import Client
from temporalio.worker import Interceptor, Worker

from temporal_boost.temporal import config


def _positive_int_option(name: str, value: int | None, default: int) -> int:
    selected = default if value is None else value
    if isinstance(selected, bool) or not isinstance(selected, int):
        raise TypeError(f"{name} must be an integer")
    if selected <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return selected


class TemporalWorkerBuilder:
    def __init__(  # noqa: PLR0913
        self,
        task_queue: str,
        *,
        debug_mode: bool = False,
        max_concurrent_workflow_tasks: int | None = None,
        max_concurrent_activities: int | None = None,
        max_concurrent_local_activities: int | None = None,
        max_concurrent_workflow_task_polls: int | None = None,
        nonsticky_to_sticky_poll_ratio: float | None = None,
        max_concurrent_activity_task_polls: int | None = None,
        graceful_shutdown_timeout: timedelta | None = None,
        **kwargs: Any,
    ) -> None:
        self._graceful_shutdown_timeout = (
            config.GRACEFUL_SHUTDOWN_TIMEOUT if graceful_shutdown_timeout is None else graceful_shutdown_timeout
        )
        if self._graceful_shutdown_timeout < timedelta():
            raise ValueError("graceful_shutdown_timeout must be non-negative")

        self._client: Client | None = None
        self.task_queue = task_queue

        self._debug_mode = debug_mode

        self._max_concurrent_workflow_tasks = _positive_int_option(
            "max_concurrent_workflow_tasks", max_concurrent_workflow_tasks, config.MAX_CONCURRENT_WORKFLOW_TASKS
        )
        self._max_concurrent_activities = _positive_int_option(
            "max_concurrent_activities", max_concurrent_activities, config.MAX_CONCURRENT_ACTIVITIES
        )
        self._max_concurrent_local_activities = _positive_int_option(
            "max_concurrent_local_activities", max_concurrent_local_activities, config.MAX_CONCURRENT_LOCAL_ACTIVITIES
        )
        self._max_concurrent_workflow_task_polls = _positive_int_option(
            "max_concurrent_workflow_task_polls", max_concurrent_workflow_task_polls, config.MAX_WORKFLOW_TASK_POLLS
        )
        self._max_concurrent_activity_task_polls = _positive_int_option(
            "max_concurrent_activity_task_polls", max_concurrent_activity_task_polls, config.MAX_ACTIVITY_TASK_POLLS
        )
        self._nonsticky_to_sticky_poll_ratio = (
            config.NONSTICKY_STICKY_RATIO if nonsticky_to_sticky_poll_ratio is None else nonsticky_to_sticky_poll_ratio
        )
        if isinstance(self._nonsticky_to_sticky_poll_ratio, bool) or not isinstance(
            self._nonsticky_to_sticky_poll_ratio, (int, float)
        ):
            raise TypeError("nonsticky_to_sticky_poll_ratio must be a number")
        if not isfinite(self._nonsticky_to_sticky_poll_ratio) or self._nonsticky_to_sticky_poll_ratio < 0:
            raise ValueError("nonsticky_to_sticky_poll_ratio must be finite and non-negative")

        self._activities: list[Callable[..., Any]] = []
        self._workflows: list[type] = []
        self._interceptors: list[Interceptor] = []

        self._worker_kwargs = kwargs

    @property
    def client(self) -> Client:
        if not self._client:
            raise RuntimeError
        return self._client

    def set_client(self, client: Client | None) -> None:
        self._client = client

    def set_activities(self, activities: list[Callable[..., Any]]) -> None:
        self._activities = activities

    def set_workflows(self, workflows: list[type]) -> None:
        self._workflows = workflows

    def set_interceptors(self, interceptors: list[Interceptor]) -> None:
        self._interceptors = interceptors

    def build(self) -> Worker:
        return Worker(
            client=self.client,
            task_queue=self.task_queue,
            activities=self._activities,
            workflows=self._workflows,
            max_concurrent_workflow_tasks=self._max_concurrent_workflow_tasks,
            max_concurrent_activities=self._max_concurrent_activities,
            max_concurrent_local_activities=self._max_concurrent_local_activities,
            max_concurrent_workflow_task_polls=self._max_concurrent_workflow_task_polls,
            nonsticky_to_sticky_poll_ratio=self._nonsticky_to_sticky_poll_ratio,
            max_concurrent_activity_task_polls=self._max_concurrent_activity_task_polls,
            graceful_shutdown_timeout=self._graceful_shutdown_timeout,
            debug_mode=self._debug_mode,
            interceptors=self._interceptors,
            **self._worker_kwargs,
        )
