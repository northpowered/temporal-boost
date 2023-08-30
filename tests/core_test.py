from temporal_boost import BoostApp
from temporal_boost.sample_t_objects import (
    test_boost_activity_1 as t_act_1
)


def test_init():
    app = BoostApp()
    app.add_worker("test_worker_1", "test_queue_1", activities=[t_act_1])
    assert app.registered_workers[0].name == "test_worker_1"