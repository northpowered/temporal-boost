from temporal_boost.common import DEFAULT_LOGGING_CONFIG


class TestCommon:
    def test_default_logging_config_structure(self):
        assert isinstance(DEFAULT_LOGGING_CONFIG, dict)
        assert "version" in DEFAULT_LOGGING_CONFIG
        assert "disable_existing_loggers" in DEFAULT_LOGGING_CONFIG
        assert "formatters" in DEFAULT_LOGGING_CONFIG
        assert "handlers" in DEFAULT_LOGGING_CONFIG
        assert "root" in DEFAULT_LOGGING_CONFIG
        assert "loggers" in DEFAULT_LOGGING_CONFIG

    def test_default_logging_config_version(self):
        assert DEFAULT_LOGGING_CONFIG["version"] == 1

    def test_default_logging_config_disable_existing_loggers(self):
        assert DEFAULT_LOGGING_CONFIG["disable_existing_loggers"] is False

    def test_default_logging_config_formatters(self):
        assert "default" in DEFAULT_LOGGING_CONFIG["formatters"]
        formatter = DEFAULT_LOGGING_CONFIG["formatters"]["default"]
        assert "format" in formatter
        assert "datefmt" in formatter

    def test_default_logging_config_handlers(self):
        assert "default" in DEFAULT_LOGGING_CONFIG["handlers"]
        handler = DEFAULT_LOGGING_CONFIG["handlers"]["default"]
        assert "class" in handler
        assert handler["class"] == "logging.StreamHandler"
        assert "formatter" in handler
        assert handler["formatter"] == "default"

    def test_default_logging_config_root(self):
        root = DEFAULT_LOGGING_CONFIG["root"]
        assert "level" in root
        assert root["level"] == "DEBUG"
        assert "handlers" in root
        assert "default" in root["handlers"]

    def test_default_logging_config_loggers(self):
        loggers = DEFAULT_LOGGING_CONFIG["loggers"]
        assert "" in loggers
        assert "uvicorn" in loggers
        assert "hypercorn" in loggers
        assert "_granian" in loggers
        assert "faststream" in loggers
        assert "temporalio" in loggers

    def test_default_logging_config_logger_levels(self):
        loggers = DEFAULT_LOGGING_CONFIG["loggers"]
        for logger_name, logger_config in loggers.items():
            assert "level" in logger_config
            assert logger_config["level"] == "DEBUG"

