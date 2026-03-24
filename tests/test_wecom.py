# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import pytest

from wechat_oa_reader.wecom import WeComClient


class _MockResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _MockAsyncClient:
    get_responses: list[dict] = []
    post_responses: list[dict] = []
    get_calls: list[dict] = []
    post_calls: list[dict] = []

    def __init__(self, *args, **kwargs) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, **kwargs):
        self.__class__.get_calls.append({"url": url, **kwargs})
        if self.__class__.get_responses:
            return _MockResponse(self.__class__.get_responses.pop(0))
        return _MockResponse({})

    async def post(self, url: str, **kwargs):
        self.__class__.post_calls.append({"url": url, **kwargs})
        if self.__class__.post_responses:
            return _MockResponse(self.__class__.post_responses.pop(0))
        return _MockResponse({})


def _reset_httpx_mock() -> None:
    _MockAsyncClient.get_responses = []
    _MockAsyncClient.post_responses = []
    _MockAsyncClient.get_calls = []
    _MockAsyncClient.post_calls = []


@pytest.mark.asyncio
async def test_get_access_token(monkeypatch) -> None:
    _reset_httpx_mock()
    _MockAsyncClient.get_responses = [
        {"errcode": 0, "errmsg": "ok", "access_token": "test-token-123", "expires_in": 7200}
    ]
    monkeypatch.setattr("wechat_oa_reader.wecom.httpx.AsyncClient", _MockAsyncClient)

    client = WeComClient(corp_id="corp-1", agent_secret="secret-1", agent_id="1000001")
    token = await client.get_access_token()

    assert token == "test-token-123"


@pytest.mark.asyncio
async def test_get_access_token_error(monkeypatch) -> None:
    _reset_httpx_mock()
    _MockAsyncClient.get_responses = [{"errcode": 40013, "errmsg": "invalid corpid"}]
    monkeypatch.setattr("wechat_oa_reader.wecom.httpx.AsyncClient", _MockAsyncClient)

    client = WeComClient(corp_id="bad-corp", agent_secret="secret-1", agent_id="1000001")
    with pytest.raises(RuntimeError, match="invalid corpid"):
        await client.get_access_token()


@pytest.mark.asyncio
async def test_send_text(monkeypatch) -> None:
    _reset_httpx_mock()
    _MockAsyncClient.get_responses = [{"errcode": 0, "access_token": "tok", "expires_in": 7200}]
    _MockAsyncClient.post_responses = [{"errcode": 0, "errmsg": "ok"}]
    monkeypatch.setattr("wechat_oa_reader.wecom.httpx.AsyncClient", _MockAsyncClient)

    client = WeComClient(corp_id="corp-1", agent_secret="secret-1", agent_id="1000001")
    result = await client.send_text("hello world", to_user="@all")

    assert result == {"errcode": 0, "errmsg": "ok"}
    assert len(_MockAsyncClient.post_calls) == 1
    post_call = _MockAsyncClient.post_calls[0]
    assert "message/send" in post_call["url"]
    assert "access_token=tok" in post_call["url"]
    assert post_call["json"] == {
        "touser": "@all",
        "msgtype": "text",
        "agentid": "1000001",
        "text": {"content": "hello world"},
    }


@pytest.mark.asyncio
async def test_token_caching(monkeypatch) -> None:
    _reset_httpx_mock()
    _MockAsyncClient.get_responses = [{"errcode": 0, "access_token": "cached-tok", "expires_in": 7200}]
    monkeypatch.setattr("wechat_oa_reader.wecom.httpx.AsyncClient", _MockAsyncClient)

    client = WeComClient(corp_id="corp-1", agent_secret="secret-1", agent_id="1000001")
    token_1 = await client.get_access_token()
    token_2 = await client.get_access_token()

    assert token_1 == "cached-tok"
    assert token_2 == "cached-tok"
    assert len(_MockAsyncClient.get_calls) == 1


@pytest.mark.asyncio
async def test_token_cache_expired(monkeypatch) -> None:
    class _Clock:
        def __init__(self, now: float) -> None:
            self.now = now

        def time(self) -> float:
            return self.now

    _reset_httpx_mock()
    _MockAsyncClient.get_responses = [
        {"errcode": 0, "access_token": "tok-1", "expires_in": 7200},
        {"errcode": 0, "access_token": "tok-2", "expires_in": 7200},
    ]
    monkeypatch.setattr("wechat_oa_reader.wecom.httpx.AsyncClient", _MockAsyncClient)

    clock = _Clock(1000)
    monkeypatch.setattr("wechat_oa_reader.wecom.time.time", clock.time)

    client = WeComClient(corp_id="corp-1", agent_secret="secret-1", agent_id="1000001")
    token_1 = await client.get_access_token()
    clock.now = 1000 + 7201
    token_2 = await client.get_access_token()

    assert token_1 == "tok-1"
    assert token_2 == "tok-2"
    assert len(_MockAsyncClient.get_calls) == 2


@pytest.mark.asyncio
async def test_upload_media(monkeypatch) -> None:
    _reset_httpx_mock()
    _MockAsyncClient.get_responses = [{"errcode": 0, "access_token": "tok", "expires_in": 7200}]
    _MockAsyncClient.post_responses = [{"errcode": 0, "type": "image", "media_id": "mid-123", "created_at": "1380000000"}]
    monkeypatch.setattr("wechat_oa_reader.wecom.httpx.AsyncClient", _MockAsyncClient)

    client = WeComClient(corp_id="corp-1", agent_secret="secret-1", agent_id="1000001")
    media_id = await client.upload_media(b"\x89PNG fake image data", "test.png")

    assert media_id == "mid-123"
    assert len(_MockAsyncClient.post_calls) == 1
    post_call = _MockAsyncClient.post_calls[0]
    assert "media/upload" in post_call["url"]
    assert "type=image" in post_call["url"]
    assert "access_token=tok" in post_call["url"]
    # Should have files parameter
    assert "files" in post_call


@pytest.mark.asyncio
async def test_upload_media_error(monkeypatch) -> None:
    _reset_httpx_mock()
    _MockAsyncClient.get_responses = [{"errcode": 0, "access_token": "tok", "expires_in": 7200}]
    _MockAsyncClient.post_responses = [{"errcode": 40004, "errmsg": "invalid media type"}]
    monkeypatch.setattr("wechat_oa_reader.wecom.httpx.AsyncClient", _MockAsyncClient)

    client = WeComClient(corp_id="corp-1", agent_secret="secret-1", agent_id="1000001")
    with pytest.raises(RuntimeError, match="invalid media type"):
        await client.upload_media(b"bad data", "test.xyz")


@pytest.mark.asyncio
async def test_send_image(monkeypatch) -> None:
    _reset_httpx_mock()
    _MockAsyncClient.get_responses = [{"errcode": 0, "access_token": "tok", "expires_in": 7200}]
    _MockAsyncClient.post_responses = [{"errcode": 0, "errmsg": "ok"}]
    monkeypatch.setattr("wechat_oa_reader.wecom.httpx.AsyncClient", _MockAsyncClient)

    client = WeComClient(corp_id="corp-1", agent_secret="secret-1", agent_id="1000001")
    result = await client.send_image("mid-123", to_user="@all")

    assert result == {"errcode": 0, "errmsg": "ok"}
    assert len(_MockAsyncClient.post_calls) == 1
    post_call = _MockAsyncClient.post_calls[0]
    assert "message/send" in post_call["url"]
    assert post_call["json"] == {
        "touser": "@all",
        "msgtype": "image",
        "agentid": "1000001",
        "image": {"media_id": "mid-123"},
    }


@pytest.mark.asyncio
async def test_custom_base_url(monkeypatch) -> None:
    """base_url should replace the default qyapi.weixin.qq.com prefix."""
    _reset_httpx_mock()
    _MockAsyncClient.get_responses = [
        {"errcode": 0, "access_token": "tok", "expires_in": 7200}
    ]
    _MockAsyncClient.post_responses = [{"errcode": 0, "errmsg": "ok"}]
    monkeypatch.setattr("wechat_oa_reader.wecom.httpx.AsyncClient", _MockAsyncClient)

    client = WeComClient(
        corp_id="corp-1", agent_secret="secret-1", agent_id="1000001",
        base_url="https://proxy.example.com",
    )
    await client.send_text("hello")

    # GET for token should use custom base URL
    assert _MockAsyncClient.get_calls[0]["url"].startswith("https://proxy.example.com/")
    # POST for send should use custom base URL
    assert _MockAsyncClient.post_calls[0]["url"].startswith("https://proxy.example.com/")


@pytest.mark.asyncio
async def test_extra_headers_passed(monkeypatch) -> None:
    """extra_headers should be forwarded to httpx.AsyncClient."""
    init_kwargs_captured = []

    class _CapturingMockClient(_MockAsyncClient):
        get_responses = [{"errcode": 0, "access_token": "tok", "expires_in": 7200}]
        get_calls = []
        post_calls = []
        post_responses = []

        def __init__(self, *args, **kwargs):
            init_kwargs_captured.append(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("wechat_oa_reader.wecom.httpx.AsyncClient", _CapturingMockClient)

    client = WeComClient(
        corp_id="corp-1", agent_secret="secret-1", agent_id="1000001",
        extra_headers={"X-Proxy-Key": "secret"},
    )
    await client.get_access_token()

    assert len(init_kwargs_captured) >= 1
    assert init_kwargs_captured[0].get("headers") == {"X-Proxy-Key": "secret"}
