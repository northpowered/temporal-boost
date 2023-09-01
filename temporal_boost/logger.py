import loguru
import logging
import sys
from dataclasses import dataclass
import typing


@dataclass
class BoostLoggerConfig:

    def _default_formatter(record):
        base_fmt = "{message}"
        return base_fmt

    sink: typing.TextIO = sys.stdout
    level: str = "DEBUG"
    json: bool = True
    formatter: typing.Callable | str = _default_formatter
    multiprocess_safe: bool = True
    bind_extra: dict | None = None


class BoostLogger:

    def __init__(self, config: BoostLoggerConfig = BoostLoggerConfig()) -> None:
        self.config = config

        loguru.logger.remove()

    def get_default_logger(self) -> logging.Logger:
        loguru.logger.add(
            sink=self.config.sink,
            level=self.config.level,
            format=self.config.formatter,
            serialize=self.config.json,
            enqueue=self.config.multiprocess_safe
        )
        if self.config.bind_extra:
            logger = loguru.logger.bind(spam="eggs")
        else:
            logger = loguru.logger

        return logger
