from temporal_boost import BoostApp

from temporal_boost.sample_t_objects import (
    test_boost_activity_1,
    test_boost_activity_2
)

app = BoostApp()

app.add_worker("worker_1", "task_q_1", activities=[test_boost_activity_1])
app.add_worker("worker_2", "task_q_2", activities=[test_boost_activity_2])

app.run()
