# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from mcp.server.fastmcp import FastMCP

from wechat_oa_reader.models import WeComMessage, WeComUser
from wechat_oa_reader.wecom_mcp import (
    check_status_handler,
    create_mcp_server,
    get_messages_handler,
    get_replies_handler,
    list_users_handler,
    send_image_handler,
    send_message_handler,
)


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    root = Path.cwd() / "test_tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"case-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.get_access_token = AsyncMock()
    client.send_text = AsyncMock()
    client.upload_media = AsyncMock()
    client.send_image = AsyncMock()
    return client


@pytest.fixture
def mock_store() -> MagicMock:
    store = MagicMock()
    store.find_user_by_name = MagicMock()
    store.save_message = MagicMock()
    store.list_users = MagicMock()
    store.get_messages = MagicMock()
    store.get_replies = MagicMock()
    return store


def _extract_tool_names(server: FastMCP) -> set[str]:
    names: set[str] = set()

    tools_attr = getattr(server, "tools", None)
    if isinstance(tools_attr, dict):
        names.update(str(k) for k in tools_attr.keys())
    elif isinstance(tools_attr, list):
        for item in tools_attr:
            name = getattr(item, "name", None)
            if isinstance(name, str):
                names.add(name)

    for attr_name in ("_tools", "_tool_registry"):
        attr = getattr(server, attr_name, None)
        if isinstance(attr, dict):
            names.update(str(k) for k in attr.keys())

    tool_manager = getattr(server, "_tool_manager", None)
    if tool_manager is not None:
        for attr_name in ("tools", "_tools"):
            attr = getattr(tool_manager, attr_name, None)
            if isinstance(attr, dict):
                names.update(str(k) for k in attr.keys())

    return names


def _make_message(
    *,
    msg_id: str,
    from_user: str,
    to_user: str,
    direction: Literal["sent", "received"],
    content: str,
    create_time: int = 1_700_000_000,
    msg_type: str = "text",
) -> WeComMessage:
    return WeComMessage(
        msg_id=msg_id,
        msg_type=msg_type,
        from_user=from_user,
        to_user=to_user,
        content=content,
        create_time=create_time,
        direction=direction,
    )


class TestMcpServerCreation:
    def test_create_server_returns_fastmcp(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        server = create_mcp_server(mock_client, mock_store)
        assert isinstance(server, FastMCP)

    def test_server_has_expected_tools(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        server = create_mcp_server(mock_client, mock_store)
        tool_names = _extract_tool_names(server)
        expected = {"check_status", "send_message", "send_image", "list_users", "get_messages", "get_replies"}
        assert expected.issubset(tool_names)


class TestCheckStatus:
    async def test_check_status_success(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_client.get_access_token.return_value = "token-xxx"

        result = await check_status_handler(mock_client, mock_store)

        mock_client.get_access_token.assert_awaited_once()
        assert "connect" in result.lower() or "ok" in result.lower()

    async def test_check_status_failure(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_client.get_access_token.side_effect = RuntimeError("boom")

        result = await check_status_handler(mock_client, mock_store)

        mock_client.get_access_token.assert_awaited_once()
        assert "error" in result.lower() or "fail" in result.lower()


class TestSendMessage:
    async def test_send_to_all(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_client.send_text.return_value = {"errcode": 0}

        result = await send_message_handler(mock_client, mock_store, content="hello team", to="@all")

        mock_client.send_text.assert_awaited_once_with("hello team", "@all")
        mock_store.save_message.assert_called_once()
        assert "@all" in result or "sent" in result.lower()

    async def test_send_to_named_user(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_store.find_user_by_name.return_value = WeComUser(userid="zhangsan", name="张三")
        mock_client.send_text.return_value = {"errcode": 0}

        result = await send_message_handler(mock_client, mock_store, content="你好", to="张三")

        mock_store.find_user_by_name.assert_called_once_with("张三")
        mock_client.send_text.assert_awaited_once_with("你好", "zhangsan")
        mock_store.save_message.assert_called_once()
        assert "张三" in result or "zhangsan" in result or "sent" in result.lower()

    async def test_send_to_unknown_user(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_store.find_user_by_name.return_value = None

        result = await send_message_handler(mock_client, mock_store, content="hello", to="Nobody")

        mock_store.find_user_by_name.assert_called_once_with("Nobody")
        mock_client.send_text.assert_not_called()
        mock_store.save_message.assert_not_called()
        assert "not found" in result.lower() or "unknown" in result.lower() or "error" in result.lower()


class TestListUsers:
    async def test_list_users_with_results(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_store.list_users.return_value = [
            WeComUser(userid="u1", name="Alice", department="Tech"),
            WeComUser(userid="u2", name="Bob", department="Ops"),
        ]

        result = await list_users_handler(mock_client, mock_store, department_id=1)

        mock_store.list_users.assert_called_once()
        assert "Alice" in result
        assert "Bob" in result

    async def test_list_users_empty(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_store.list_users.return_value = []

        result = await list_users_handler(mock_client, mock_store, department_id=1)

        mock_store.list_users.assert_called_once()
        assert "no" in result.lower() and "user" in result.lower()


class TestGetMessages:
    async def test_get_messages_default(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_store.get_messages.return_value = [
            _make_message(msg_id="m1", from_user="u1", to_user="u2", direction="sent", content="hello"),
        ]

        result = await get_messages_handler(mock_client, mock_store)

        mock_store.get_messages.assert_called_once()
        assert "hello" in result

    async def test_get_messages_with_from_user(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_store.get_messages.return_value = []

        with patch("wechat_oa_reader.wecom_mcp.time.time", return_value=1_700_000_000):
            await get_messages_handler(
                mock_client,
                mock_store,
                from_user="zhangsan",
                limit=10,
                since_minutes=15,
            )

        _, kwargs = mock_store.get_messages.call_args
        assert kwargs["from_user"] == "zhangsan"
        assert kwargs["limit"] == 10
        assert isinstance(kwargs.get("since"), int)

    async def test_get_messages_empty(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_store.get_messages.return_value = []

        result = await get_messages_handler(mock_client, mock_store, from_user="", limit=20, since_minutes=0)

        assert "no" in result.lower() and "message" in result.lower()


class TestGetReplies:
    async def test_get_replies_default(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_store.get_replies.return_value = [
            _make_message(msg_id="m2", from_user="u2", to_user="me", direction="received", content="received hi"),
        ]

        result = await get_replies_handler(mock_client, mock_store, since_minutes=60, limit=50)

        mock_store.get_replies.assert_called_once()
        assert "received hi" in result

    async def test_get_replies_empty(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_store.get_replies.return_value = []

        result = await get_replies_handler(mock_client, mock_store, since_minutes=60, limit=50)

        assert "no" in result.lower() and "repl" in result.lower()


class TestSendImage:
    async def test_send_image_to_all(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_client.upload_media.return_value = "media-123"
        mock_client.send_image.return_value = {"errcode": 0}
        image_b64 = "aVZCT1J3MEtHZ29BQQ=="  # fake base64

        result = await send_image_handler(mock_client, mock_store, image_base64=image_b64, filename="test.png", to="@all")

        mock_client.upload_media.assert_awaited_once()
        mock_client.send_image.assert_awaited_once_with("media-123", "@all")
        mock_store.save_message.assert_called_once()
        assert "sent" in result.lower() or "image" in result.lower()

    async def test_send_image_to_named_user(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_store.find_user_by_name.return_value = WeComUser(userid="zhangsan", name="张三")
        mock_client.upload_media.return_value = "media-456"
        mock_client.send_image.return_value = {"errcode": 0}

        result = await send_image_handler(mock_client, mock_store, image_base64="AAAA", filename="pic.png", to="张三")

        mock_store.find_user_by_name.assert_called_once_with("张三")
        mock_client.send_image.assert_awaited_once_with("media-456", "zhangsan")

    async def test_send_image_user_not_found(self, mock_client: MagicMock, mock_store: MagicMock) -> None:
        mock_store.find_user_by_name.return_value = None

        result = await send_image_handler(mock_client, mock_store, image_base64="AAAA", filename="pic.png", to="Nobody")

        mock_client.upload_media.assert_not_called()
        assert "not found" in result.lower()
