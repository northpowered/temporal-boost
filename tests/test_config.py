import math
import os
from datetime import timedelta
from unittest.mock import patch

import pytest

from temporal_boost.temporal import config


class TestConfigUtilityFunctions:
    def test_get_env_bool_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert config.get_env_bool("NONEXISTENT", default=False) is False
            assert config.get_env_bool("NONEXISTENT", default=True) is True

    def test_get_env_bool_true_values(self):
        true_values = ["true", "True", "TRUE", "1", "yes", "Yes", "YES"]
        for value in true_values:
            with patch.dict(os.environ, {"TEST_VAR": value}, clear=False):
                assert config.get_env_bool("TEST_VAR", default=False) is True

    def test_get_env_bool_false_values(self):
        false_values = ["false", "False", "FALSE", "0", "no", "No", "NO", "anything_else"]
        for value in false_values:
            with patch.dict(os.environ, {"TEST_VAR": value}, clear=False):
                assert config.get_env_bool("TEST_VAR", default=True) is False

    def test_get_env_int_valid(self):
        with patch.dict(os.environ, {"TEST_VAR": "123"}, clear=False):
            assert config.get_env_int("TEST_VAR", default=0) == 123

    def test_get_env_int_invalid(self):
        with patch.dict(os.environ, {"TEST_VAR": "not_a_number"}, clear=False):
            assert config.get_env_int("TEST_VAR", default=42) == 42

    def test_get_env_int_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            assert config.get_env_int("NONEXISTENT", default=99) == 99

    def test_get_env_float_valid(self):
        with patch.dict(os.environ, {"TEST_VAR": "123.45"}, clear=False):
            assert math.isclose(config.get_env_float("TEST_VAR", default=0.0), 123.45)

    def test_get_env_float_invalid(self):
        with patch.dict(os.environ, {"TEST_VAR": "not_a_number"}, clear=False):
            assert math.isclose(config.get_env_float("TEST_VAR", default=3.14), 3.14)

    def test_get_env_float_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            assert math.isclose(config.get_env_float("NONEXISTENT", default=2.71), 2.71)

    def test_config_constants_exist(self):
        assert hasattr(config, "TARGET_HOST")
        assert hasattr(config, "CLIENT_NAMESPACE")
        assert hasattr(config, "CLIENT_TLS")
        assert hasattr(config, "CLIENT_API_KEY")
        assert hasattr(config, "CLIENT_IDENTITY")
        assert hasattr(config, "USE_PYDANTIC_DATA_CONVERTER")
        assert hasattr(config, "MAX_CONCURRENT_WORKFLOW_TASKS")
        assert hasattr(config, "MAX_CONCURRENT_ACTIVITIES")
        assert hasattr(config, "MAX_CONCURRENT_LOCAL_ACTIVITIES")
        assert hasattr(config, "MAX_WORKFLOW_TASK_POLLS")
        assert hasattr(config, "MAX_ACTIVITY_TASK_POLLS")
        assert hasattr(config, "NONSTICKY_STICKY_RATIO")
        assert hasattr(config, "GRACEFUL_SHUTDOWN_TIMEOUT")
        assert hasattr(config, "PROMETHEUS_BIND_ADDRESS")
        assert hasattr(config, "PROMETHEUS_COUNTERS_TOTAL_SUFFIX")
        assert hasattr(config, "PROMETHEUS_UNIT_SUFFIX")
        assert hasattr(config, "PROMETHEUS_DURATIONS_AS_SECONDS")

    def test_config_default_values(self):
        assert config.TARGET_HOST == "localhost:7233"
        assert config.CLIENT_NAMESPACE == "default"
        assert config.CLIENT_TLS is False
        assert config.MAX_CONCURRENT_WORKFLOW_TASKS == 300
        assert config.MAX_CONCURRENT_ACTIVITIES == 300
        assert config.MAX_CONCURRENT_LOCAL_ACTIVITIES == 100
        assert config.MAX_WORKFLOW_TASK_POLLS == 10
        assert config.MAX_ACTIVITY_TASK_POLLS == 10
        assert math.isclose(config.NONSTICKY_STICKY_RATIO, 0.2)
        assert config.GRACEFUL_SHUTDOWN_TIMEOUT == timedelta(seconds=30)
        assert config.PROMETHEUS_COUNTERS_TOTAL_SUFFIX is False
        assert config.PROMETHEUS_UNIT_SUFFIX is False
        assert config.PROMETHEUS_DURATIONS_AS_SECONDS is False

