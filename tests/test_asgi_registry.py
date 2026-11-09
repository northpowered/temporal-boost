from itertools import combinations, permutations
from unittest.mock import patch

import pytest

from temporal_boost.workers.asgi_registry import (
    ASGIWorkerRegistry,
    ASGIWorkerType,
    asgi_worker_registry,
    get_asgi_worker_class,
)


class MockASGIWorker:
    pass


class TestASGIWorkerRegistry:
    def test_init(self):
        registry = ASGIWorkerRegistry()
        assert registry._data == {}

    def test_register(self):
        registry = ASGIWorkerRegistry()

        @registry.register("test_worker")
        class TestWorker(MockASGIWorker):
            pass

        assert "test_worker" in registry._data
        assert registry._data["test_worker"] == TestWorker

    def test_register_with_packages(self):
        registry = ASGIWorkerRegistry()

        @registry.register("test_worker", packages=["os"])
        class TestWorker(MockASGIWorker):
            pass

        assert "test_worker" in registry._data

    def test_register_with_missing_package(self):
        registry = ASGIWorkerRegistry()

        @registry.register("test_worker", packages=["nonexistent_package_12345"])
        class TestWorker(MockASGIWorker):
            pass

        assert "test_worker" not in registry._data

    def test_get_existing(self):
        registry = ASGIWorkerRegistry()

        @registry.register("test_worker")
        class TestWorker(MockASGIWorker):
            pass

        worker_class = registry.get("test_worker")
        assert worker_class == TestWorker

    def test_get_nonexistent(self):
        registry = ASGIWorkerRegistry()

        with pytest.raises(RuntimeError, match="is not available"):
            registry.get("nonexistent")

    def test_available_keys(self):
        registry = ASGIWorkerRegistry()

        @registry.register("worker1")
        class Worker1(MockASGIWorker):
            pass

        @registry.register("worker2")
        class Worker2(MockASGIWorker):
            pass

        keys = registry.available_keys()
        assert "worker1" in keys
        assert "worker2" in keys
        assert len(keys) == 2


class TestASGIWorkerType:
    def test_enum_values(self):
        assert ASGIWorkerType.uvicorn.value == "uvicorn"
        assert ASGIWorkerType.hypercorn.value == "hypercorn"
        assert ASGIWorkerType.granian.value == "granian"
        assert ASGIWorkerType.auto.value == "auto"


class TestGetASGIWorkerClass:
    def test_get_uvicorn(self):
        with patch.object(asgi_worker_registry, "get") as mock_get:
            mock_get.return_value = MockASGIWorker
            worker_class = get_asgi_worker_class(ASGIWorkerType.uvicorn)
            mock_get.assert_called_once_with("uvicorn")
            assert worker_class == MockASGIWorker

    def test_get_hypercorn(self):
        with patch.object(asgi_worker_registry, "get") as mock_get:
            mock_get.return_value = MockASGIWorker
            worker_class = get_asgi_worker_class(ASGIWorkerType.hypercorn)
            mock_get.assert_called_once_with("hypercorn")
            assert worker_class == MockASGIWorker

    def test_get_granian(self):
        with patch.object(asgi_worker_registry, "get") as mock_get:
            mock_get.return_value = MockASGIWorker
            worker_class = get_asgi_worker_class(ASGIWorkerType.granian)
            mock_get.assert_called_once_with("granian")
            assert worker_class == MockASGIWorker

    def test_get_auto_with_uvicorn_available(self):
        with patch.object(asgi_worker_registry, "available_keys") as mock_keys:
            mock_keys.return_value = ["uvicorn", "hypercorn"]

            with patch.object(asgi_worker_registry, "get") as mock_get:
                mock_get.return_value = MockASGIWorker
                worker_class = get_asgi_worker_class(ASGIWorkerType.auto)
                mock_get.assert_called_once_with("uvicorn")
                assert worker_class == MockASGIWorker

    def test_get_auto_without_uvicorn(self):
        with patch.object(asgi_worker_registry, "available_keys") as mock_keys:
            mock_keys.return_value = ["hypercorn", "granian"]

            with patch.object(asgi_worker_registry, "get") as mock_get:
                mock_get.return_value = MockASGIWorker
                worker_class = get_asgi_worker_class(ASGIWorkerType.auto)
                mock_get.assert_called_once_with("granian")
                assert worker_class == MockASGIWorker

    def test_get_auto_with_no_workers(self):
        with patch.object(asgi_worker_registry, "available_keys") as mock_keys:
            mock_keys.return_value = []

            with pytest.raises(RuntimeError, match="No ASGI worker implementation is available"):
                get_asgi_worker_class(ASGIWorkerType.auto)



BUILTINS = ("uvicorn", "granian", "hypercorn")
ORDERS = [order for size in range(1, 4) for subset in combinations(BUILTINS, size) for order in permutations(subset)]


@pytest.mark.parametrize("order", ORDERS)
def test_auto_priority_is_independent_of_registration_order(order, monkeypatch):
    registry = ASGIWorkerRegistry()
    classes = {key: type(f"Worker_{key}", (MockASGIWorker,), {}) for key in order}
    for key in order:
        registry.register(key)(classes[key])
    monkeypatch.setattr("temporal_boost.workers.asgi_registry.asgi_worker_registry", registry)
    expected = next(key for key in BUILTINS if key in order)
    assert get_asgi_worker_class(ASGIWorkerType.auto) is classes[expected]
    for key in order:
        assert get_asgi_worker_class(ASGIWorkerType(key)) is classes[key]


@pytest.mark.parametrize("order", [("zeta", "alpha"), ("alpha", "zeta")])
def test_custom_fallback_is_lexical(order, monkeypatch):
    registry = ASGIWorkerRegistry()
    classes = {key: type(key, (MockASGIWorker,), {}) for key in order}
    for key in order:
        registry.register(key)(classes[key])
    monkeypatch.setattr("temporal_boost.workers.asgi_registry.asgi_worker_registry", registry)
    assert get_asgi_worker_class(ASGIWorkerType.auto) is classes["alpha"]
    registry.register("hypercorn")(MockASGIWorker)
    assert get_asgi_worker_class(ASGIWorkerType.auto) is MockASGIWorker


@pytest.mark.parametrize("key", ["uvicorn", "granian", "hypercorn", "custom"])
def test_duplicate_registration_is_idempotent_but_cannot_replace(key):
    registry = ASGIWorkerRegistry()
    registry.register(key)(MockASGIWorker)
    assert registry.register(key)(MockASGIWorker) is MockASGIWorker
    replacement = type("Replacement", (MockASGIWorker,), {})
    with pytest.raises(ValueError, match="already registered"):
        registry.register(key)(replacement)
    assert registry.get(key) is MockASGIWorker


@pytest.mark.parametrize("key", BUILTINS)
def test_missing_optional_dependency_does_not_register_backend(key):
    registry = ASGIWorkerRegistry()
    with patch("builtins.__import__", side_effect=ImportError("optional backend missing")):
        assert registry.register(key, packages=[key])(MockASGIWorker) is MockASGIWorker
    assert registry.available_keys() == []
