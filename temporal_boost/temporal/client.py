from typing import TYPE_CHECKING, Any

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.runtime import Runtime

from temporal_boost.temporal import config


if TYPE_CHECKING:
    from temporalio.converter import DataConverter


class TemporalClientBuilder:
    """Configure a client; an explicit data_converter takes priority over the Pydantic flag."""

    def __init__(  # noqa: PLR0913
        self,
        target_host: str | None = None,
        namespace: str | None = None,
        api_key: str | None = None,
        identity: str | None = None,
        *,
        tls: bool | None = None,
        use_pydantic_data_converter: bool | None = None,
        **kwargs: Any,
    ) -> None:
        self._target_host = target_host or config.TARGET_HOST
        self._namespace = namespace or config.CLIENT_NAMESPACE
        self._api_key = api_key or config.CLIENT_API_KEY
        self._tls = tls if tls is not None else config.CLIENT_TLS
        self._identity = identity or config.CLIENT_IDENTITY

        self._runtime: Runtime | None = None

        use_pydantic = (
            config.USE_PYDANTIC_DATA_CONVERTER if use_pydantic_data_converter is None else use_pydantic_data_converter
        )
        self._data_converter: DataConverter | None = pydantic_data_converter if use_pydantic else None

        self._client_kwargs = kwargs

    def set_runtime(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def set_target_host(self, target_host: str) -> None:
        self._target_host = target_host

    def set_namespace(self, namespace: str) -> None:
        self._namespace = namespace

    def set_api_key(self, api_key: str) -> None:
        self._api_key = api_key

    def set_tls(self, tls: bool) -> None:
        self._tls = tls

    def set_identity(self, identity: str) -> None:
        self._identity = identity

    def set_kwargs(self, **kwargs: Any) -> None:
        self._client_kwargs.update(kwargs)

    def set_pydantic_data_converter(self, *, enabled: bool = True) -> None:
        """Enable or disable automatic Pydantic selection, preserving any explicit data_converter."""
        self._data_converter = pydantic_data_converter if enabled else None

    async def build(self) -> Client:
        if self._runtime is None:
            self._runtime = Runtime.default()

        client_kwargs = self._client_kwargs.copy()
        if self._data_converter is not None:
            client_kwargs.setdefault("data_converter", self._data_converter)

        return await Client.connect(
            target_host=self._target_host,
            namespace=self._namespace,
            api_key=self._api_key,
            tls=self._tls,
            identity=self._identity,
            runtime=self._runtime,
            **client_kwargs,
        )
