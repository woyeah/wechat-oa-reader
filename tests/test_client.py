# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import httpx
import pytest

from wechat_oa_reader.client import WeChatClient
from wechat_oa_reader.models import Credentials


def test_is_authenticated_true() -> None:
    client = WeChatClient(token="t", cookie="c")
    assert client.is_authenticated is True


def test_is_authenticated_false() -> None:
    client = WeChatClient(token=None, cookie="c")
    assert client.is_authenticated is False


def test_credentials_property() -> None:
    client = WeChatClient(token="t", cookie="c")
    creds = client.credentials
    assert creds is not None
    assert creds.token == "t"
    assert creds.cookie == "c"


@pytest.mark.asyncio
async def test_require_auth_raises(monkeypatch) -> None:
    class _UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("httpx.AsyncClient should not be created when auth is missing")

    monkeypatch.setattr("wechat_oa_reader.client.httpx.AsyncClient", _UnexpectedClient)
    client = WeChatClient()
    with pytest.raises(RuntimeError, match="Client is not authenticated"):
        await client.search_accounts("test")


@pytest.mark.asyncio
async def test_from_credentials() -> None:
    creds = Credentials(token="token-x", cookie="cookie-x", nickname="n", fakeid="f")
    client = await WeChatClient.from_credentials(creds)
    assert client.is_authenticated is True
    assert client.credentials is not None
    assert client.credentials.token == "token-x"


@pytest.mark.asyncio
async def test_check_auth_returns_false_when_not_authenticated() -> None:
    client = WeChatClient()
    assert await client.check_auth() is False


@pytest.mark.asyncio
async def test_check_auth_returns_true_when_ret_zero(monkeypatch) -> None:
    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"base_resp": {"ret": 0}}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, *args, **kwargs):
            return _Response()

    monkeypatch.setattr("wechat_oa_reader.client.httpx.AsyncClient", _FakeAsyncClient)
    client = WeChatClient(token="t", cookie="c")
    assert await client.check_auth() is True


@pytest.mark.asyncio
async def test_check_auth_returns_false_when_ret_nonzero(monkeypatch) -> None:
    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"base_resp": {"ret": 200003}}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, *args, **kwargs):
            return _Response()

    monkeypatch.setattr("wechat_oa_reader.client.httpx.AsyncClient", _FakeAsyncClient)
    client = WeChatClient(token="t", cookie="c")
    assert await client.check_auth() is False


@pytest.mark.asyncio
async def test_check_auth_returns_false_on_network_error(monkeypatch) -> None:
    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("connection failed")

    monkeypatch.setattr("wechat_oa_reader.client.httpx.AsyncClient", _FakeAsyncClient)
    client = WeChatClient(token="t", cookie="c")
    assert await client.check_auth() is False


@pytest.mark.asyncio
async def test_check_auth_uses_nonempty_query(monkeypatch) -> None:
    captured_kwargs: list[dict] = []

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"base_resp": {"ret": 0}}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, *args, **kwargs):
            captured_kwargs.append(kwargs)
            return _Response()

    monkeypatch.setattr("wechat_oa_reader.client.httpx.AsyncClient", _FakeAsyncClient)
    client = WeChatClient(token="t", cookie="c")
    assert await client.check_auth() is True
    assert captured_kwargs
    params = captured_kwargs[0]["params"]
    assert isinstance(params["query"], str)
    assert params["query"] != ""
