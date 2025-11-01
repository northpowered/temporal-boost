from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from temporal_boost.temporal.client import TemporalClientBuilder


class TestTemporalClientBuilder:
    def test_init_with_defaults(self):
        builder = TemporalClientBuilder()
        assert builder._target_host is not None
        assert builder._namespace is not None
        assert builder._runtime is None
        assert builder._data_converter is None

    def test_init_with_target_host(self):
        builder = TemporalClientBuilder(target_host="localhost:7233")
        assert builder._target_host == "localhost:7233"

    def test_init_with_namespace(self):
        builder = TemporalClientBuilder(namespace="test_namespace")
        assert builder._namespace == "test_namespace"

    def test_init_with_api_key(self):
        builder = TemporalClientBuilder(api_key="test_key")
        assert builder._api_key == "test_key"

    def test_init_with_tls(self):
        builder = TemporalClientBuilder(tls=True)
        assert builder._tls is True

    def test_init_with_identity(self):
        builder = TemporalClientBuilder(identity="test_identity")
        assert builder._identity == "test_identity"

    def test_init_with_pydantic_data_converter(self):
        builder = TemporalClientBuilder(use_pydantic_data_converter=True)
        assert builder._data_converter is not None

    def test_init_with_kwargs(self):
        builder = TemporalClientBuilder(custom_param="value")
        assert builder._client_kwargs["custom_param"] == "value"

    def test_set_runtime(self):
        builder = TemporalClientBuilder()
        runtime = MagicMock()
        builder.set_runtime(runtime)
        assert builder._runtime == runtime

    def test_set_target_host(self):
        builder = TemporalClientBuilder()
        builder.set_target_host("new_host:7233")
        assert builder._target_host == "new_host:7233"

    def test_set_namespace(self):
        builder = TemporalClientBuilder()
        builder.set_namespace("new_namespace")
        assert builder._namespace == "new_namespace"

    def test_set_api_key(self):
        builder = TemporalClientBuilder()
        builder.set_api_key("new_key")
        assert builder._api_key == "new_key"

    def test_set_tls(self):
        builder = TemporalClientBuilder()
        builder.set_tls(True)
        assert builder._tls is True

    def test_set_identity(self):
        builder = TemporalClientBuilder()
        builder.set_identity("new_identity")
        assert builder._identity == "new_identity"

    def test_set_kwargs(self):
        builder = TemporalClientBuilder()
        builder.set_kwargs(param1="value1", param2="value2")
        assert builder._client_kwargs["param1"] == "value1"
        assert builder._client_kwargs["param2"] == "value2"

    def test_set_kwargs_updates_existing(self):
        builder = TemporalClientBuilder(existing="old")
        builder.set_kwargs(existing="new", new_param="value")
        assert builder._client_kwargs["existing"] == "new"
        assert builder._client_kwargs["new_param"] == "value"

    def test_set_pydantic_data_converter(self):
        builder = TemporalClientBuilder()
        builder.set_pydantic_data_converter()
        assert builder._data_converter is not None

    @pytest.mark.asyncio
    async def test_build_with_default_runtime(self):
        builder = TemporalClientBuilder(target_host="localhost:7233")

        mock_client = AsyncMock()
        with patch("temporalio.client.Client.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_client

            client = await builder.build()

            assert client == mock_client
            mock_connect.assert_called_once()
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["target_host"] == "localhost:7233"
            assert call_kwargs["runtime"] is not None

    @pytest.mark.asyncio
    async def test_build_with_custom_runtime(self):
        builder = TemporalClientBuilder(target_host="localhost:7233")
        mock_runtime = MagicMock()
        builder.set_runtime(mock_runtime)

        mock_client = AsyncMock()
        with patch("temporalio.client.Client.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_client

            client = await builder.build()

            assert client == mock_client
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["runtime"] == mock_runtime

    @pytest.mark.asyncio
    async def test_build_with_pydantic_data_converter(self):
        builder = TemporalClientBuilder(target_host="localhost:7233")
        builder.set_pydantic_data_converter()

        mock_client = AsyncMock()
        with patch("temporalio.client.Client.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_client

            client = await builder.build()

            assert client == mock_client
            call_kwargs = mock_connect.call_args[1]
            assert "data_converter" in call_kwargs
            assert call_kwargs["data_converter"] is not None

    @pytest.mark.asyncio
    async def test_build_with_all_parameters(self):
        builder = TemporalClientBuilder(
            target_host="localhost:7233",
            namespace="test_namespace",
            api_key="test_key",
            identity="test_identity",
            tls=True,
            custom_param="value",
        )

        mock_runtime = MagicMock()
        builder.set_runtime(mock_runtime)

        mock_client = AsyncMock()
        with patch("temporalio.client.Client.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_client

            client = await builder.build()

            assert client == mock_client
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["target_host"] == "localhost:7233"
            assert call_kwargs["namespace"] == "test_namespace"
            assert call_kwargs["api_key"] == "test_key"
            assert call_kwargs["identity"] == "test_identity"
            assert call_kwargs["tls"] is True
            assert call_kwargs["custom_param"] == "value"
            assert call_kwargs["runtime"] == mock_runtime

