"""CLI subprocess fixture with observable commands and no external services."""

from temporal_boost import BaseBoostWorker, BoostApp


class ExitCodeWorker(BaseBoostWorker):
    def __init__(self, name: str, failure: BaseException | None = None) -> None:
        self.name = name
        self.failure = failure

    def run(self) -> None:
        print(f"worker:{self.name}", flush=True)  # noqa: T201
        if self.failure is not None:
            raise self.failure

    async def shutdown(self) -> None:
        pass


def greet(name: str, count: int = 1) -> str:
    message = f"Hello {name}, count={count}"
    print(message)  # noqa: T201
    return message


def make_app() -> BoostApp:
    application = BoostApp(name="exit-code-test", logger_config=None)
    for worker in (
        ExitCodeWorker("selected"),
        ExitCodeWorker("other"),
        ExitCodeWorker("broken", RuntimeError("worker failure")),
        ExitCodeWorker("exit-code", SystemExit(7)),
        ExitCodeWorker("interrupt", KeyboardInterrupt()),
    ):
        application.add_async_runtime(worker.name, worker)
    application.add_exec_method_sync("greet", greet)
    return application


app = make_app()

if __name__ == "__main__":
    app.run()
