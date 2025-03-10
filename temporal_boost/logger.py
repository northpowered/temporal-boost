import logging
import sys
import typing
from dataclasses import dataclass

import loguru


@dataclass
class BoostLoggerConfig:
    @staticmethod
    def _default_json_formatter(_: typing.Any) -> str:
        return "{message}"

    @staticmethod
    def default_plain_formatter(_: typing.Any) -> str:
        return "<green>{time:YYYY-MM-DDTHH:mm:ss}</green> | <level>{level: <8}</level> | {message}\n"

    sink: typing.TextIO = sys.stdout
    level: str = "DEBUG"
    json: bool = True
    formatter: typing.Callable | str = _default_json_formatter
    multiprocess_safe: bool = True
    bind_extra: dict | None = None


class BoostLogger:
    def __init__(self, config: BoostLoggerConfig | None = None) -> None:
        if not config:
            config = BoostLoggerConfig()

        self.config = config

        loguru.logger.remove()

    def get_default_logger(self) -> logging.Logger:
        if not self.config.json:
            self.config.formatter = BoostLoggerConfig.default_plain_formatter
        loguru.logger.add(
            sink=self.config.sink,
            level=self.config.level,
            format=self.config.formatter,
            serialize=self.config.json,
            enqueue=self.config.multiprocess_safe,
        )

        logger = loguru.logger
        if self.config.bind_extra:
            logger = loguru.logger.bind(**self.config.bind_extra)

        return logger
