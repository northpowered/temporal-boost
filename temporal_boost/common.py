DEFAULT_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["default"],
    },
    "loggers": {
        "": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "uvicorn": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "hypercorn": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "_granian": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "faststream": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "faststream.access": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "faststream.access.redis": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "asyncio": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "temporalio": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
    },
}
