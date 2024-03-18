import loguru
import logging
import sys
from dataclasses import dataclass
import typing


@dataclass
class BoostLoggerConfig:

    def _default_json_formatter(record):
        base_fmt = "{message}"
        return base_fmt

    def _default_plain_formatter(record):
        base_fmt = "<green>{time:YYYY-MM-DDTHH:mm:ss}</green> | <level>{level: <8}</level> | {message}\n"
        return base_fmt

    sink: typing.TextIO = sys.stdout
    level: str = "DEBUG"
    json: bool = True
    formatter: typing.Callable | str = _default_json_formatter
    multiprocess_safe: bool = True
    bind_extra: dict | None = None


class  BoostLogger:

    def __init__(self, config: BoostLoggerConfig = BoostLoggerConfig()) -> None:
        self.config = config

        loguru.logger.remove()

    def get_default_logger(self) -> logging.Logger:
        if not self.config.json:
            self.config.formatter = BoostLoggerConfig._default_plain_formatter
        loguru.logger.add(
            sink=self.config.sink,
            level=self.config.level,
            format=self.config.formatter,
            serialize=self.config.json,
            enqueue=self.config.multiprocess_safe
        )
        if self.config.bind_extra:
            logger = loguru.logger.bind(**self.config.bind_extra)
        else:
            logger = loguru.logger

        return logger
