from temporalio import activity
from temporalio import workflow


@activity.defn(name="test_boost_activity_1")
async def test_boost_activity_1(foo: str, bar: str) -> str:
    """
    This is doc for first activity

    Args:

        foo (str): some vaule 1
        bar (str): some value 2

    Returns:

        str: sum of these strings
    """
    return f"1_{foo}{bar}"


@activity.defn(name="test_boost_activity_2")
async def test_boost_activity_2(foo: str, bar: str) -> str:
    return f"2_{foo}{bar}"


@workflow.defn(name="TestCronWorkflow", sandboxed=False)
class TestCronWorkflow:
    @workflow.run
    async def run(self) -> None:
        print("With is cron workflow")
        return None
