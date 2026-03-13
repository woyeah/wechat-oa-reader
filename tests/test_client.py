# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

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
