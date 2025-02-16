from temporal_boost import BoostApp

from .sample_t_objects import TestCronWorkflow
from .sample_t_objects import test_boost_activity_1 as t_act_1


def test_create_worker():
    app = BoostApp()
    app.add_worker("test_worker_1", "test_queue_1", activities=[t_act_1])
    assert app.registered_workers[0].name == "test_worker_1"
    assert len(app.registered_cron_workers) == 0


def test_create_cron():
    app = BoostApp()
    app.add_worker(
        "test_worker_1",
        "test_queue_1",
        workflows=[TestCronWorkflow],
        cron_schedule="* * * * *",
        cron_runner=TestCronWorkflow.run,
    )
    assert app.registered_cron_workers[0].name == "test_worker_1"


def test_create_prohibited_worker():
    app = BoostApp()
    try:
        app.add_worker("all", "test_queue_1", activities=[t_act_1])
    except RuntimeError:
        assert True
