from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.converter import DataConverter

from temporal_boost.temporal import config
from temporal_boost.temporal.client import TemporalClientBuilder


class TestTemporalClientBuilder:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("env_enabled", [False, True])
    @pytest.mark.parametrize("use_pydantic", [None, False, True])
    async def test_pydantic_override_matrix(
        self, monkeypatch: pytest.MonkeyPatch, env_enabled: bool, use_pydantic: bool | None
    ) -> None:
        monkeypatch.setattr(config, "USE_PYDANTIC_DATA_CONVERTER", env_enabled)
        builder = TemporalClientBuilder(use_pydantic_data_converter=use_pydantic)
        builder.set_runtime(MagicMock())

        with patch("temporalio.client.Client.connect", new_callable=AsyncMock) as connect:
            await builder.build()

        enabled = env_enabled if use_pydantic is None else use_pydantic
        if enabled:
            assert connect.call_args.kwargs["data_converter"] is pydantic_data_converter
        else:
            assert "data_converter" not in connect.call_args.kwargs

    @pytest.mark.asyncio
    async def test_disable_pydantic_after_build(self) -> None:
        builder = TemporalClientBuilder(use_pydantic_data_converter=True, custom_param="value")
        builder.set_runtime(MagicMock())

        with patch("temporalio.client.Client.connect", new_callable=AsyncMock) as connect:
            await builder.build()
            builder.set_pydantic_data_converter(enabled=False)
            await builder.build()

        assert connect.call_args_list[0].kwargs["data_converter"] is pydantic_data_converter
        assert "data_converter" not in connect.call_args_list[1].kwargs
        assert connect.call_args_list[1].kwargs["custom_param"] == "value"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("env_enabled", [False, True])
    @pytest.mark.parametrize("use_pydantic", [None, False, True])
    @pytest.mark.parametrize("via_set_kwargs", [False, True])
    async def test_custom_converter_takes_priority(
        self,
        monkeypatch: pytest.MonkeyPatch,
        env_enabled: bool,
        use_pydantic: bool | None,
        via_set_kwargs: bool,
    ) -> None:
        monkeypatch.setattr(config, "USE_PYDANTIC_DATA_CONVERTER", env_enabled)
        converter = DataConverter()
        kwargs = {} if via_set_kwargs else {"data_converter": converter}
        builder = TemporalClientBuilder(use_pydantic_data_converter=use_pydantic, **kwargs)
        builder.set_runtime(MagicMock())

        with patch("temporalio.client.Client.connect", new_callable=AsyncMock) as connect:
            if via_set_kwargs:
                await builder.build()
                builder.set_kwargs(data_converter=converter)
            await builder.build()
            builder.set_pydantic_data_converter()
            await builder.build()
            builder.set_pydantic_data_converter(enabled=False)
            await builder.build()

        for call in connect.call_args_list[-3:]:
            assert call.kwargs["data_converter"] is converter

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
