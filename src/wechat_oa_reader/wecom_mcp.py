# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import base64
import os
import time
from collections.abc import Awaitable, Callable

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

from .models import WeComMessage
from .wecom import WeComClient
from .wecom_crypto import decrypt_message, parse_callback_xml, verify_signature
from .wecom_store import WeComStore


async def check_status_handler(client, store) -> str:
    """Check WeCom connection. Try get_access_token; return connected/error status."""
    _ = store
    try:
        token = await client.get_access_token()
        return f"Connected. Token: {token[:8]}..."
    except Exception as e:  # pragma: no cover - exercised in tests
        return f"Error: {e}"


async def send_message_handler(client, store, *, content: str, to: str) -> str:
    """Send message. If to != '@all', look up user by name. Save message to store."""
    if to == "@all":
        userid = "@all"
    else:
        user = store.find_user_by_name(to)
        if user is None:
            return f"User not found: {to}"
        userid = user.userid

    await client.send_text(content, userid)
    store.save_message(
        WeComMessage(
            msg_id="",
            msg_type="text",
            from_user="bot",
            to_user=userid,
            content=content,
            create_time=int(time.time()),
            direction="sent",
        )
    )
    return f"Sent to {to} ({userid})"


async def send_image_handler(client, store, *, image_base64: str, filename: str = "image.png", to: str = "@all") -> str:
    """Send image. Accepts base64-encoded image data, uploads and sends."""
    if to == "@all":
        userid = "@all"
    else:
        user = store.find_user_by_name(to)
        if user is None:
            return f"User not found: {to}"
        userid = user.userid

    image_data = base64.b64decode(image_base64)
    media_id = await client.upload_media(image_data, filename)
    await client.send_image(media_id, userid)
    store.save_message(
        WeComMessage(
            msg_id="",
            msg_type="image",
            from_user="bot",
            to_user=userid,
            content=f"[image:{filename}]",
            create_time=int(time.time()),
            direction="sent",
        )
    )
    return f"Image sent to {to} ({userid})"


async def list_users_handler(client, store, *, department_id: int = 1) -> str:
    """List cached users."""
    _ = client
    _ = department_id
    users = store.list_users()
    if not users:
        return "No users found"
    lines = [f"- {u.name} ({u.userid}) {u.department or ''}" for u in users]
    return f"Users ({len(users)}):\n" + "\n".join(lines)


async def get_messages_handler(
    client,
    store,
    *,
    from_user: str = "",
    limit: int = 20,
    since_minutes: int = 0,
) -> str:
    """Get message history."""
    _ = client
    kwargs: dict[str, str | int] = {"limit": limit}
    if from_user:
        kwargs["from_user"] = from_user
    if since_minutes > 0:
        kwargs["since"] = int(time.time()) - since_minutes * 60
    messages = store.get_messages(**kwargs)
    if not messages:
        return "No messages found"
    lines = [f"[{m.direction}] {m.from_user} -> {m.to_user}: {m.content}" for m in messages]
    return "\n".join(lines)


async def get_replies_handler(client, store, *, since_minutes: int = 60, limit: int = 50) -> str:
    """Get received replies."""
    _ = client
    kwargs: dict[str, int] = {"limit": limit}
    if since_minutes > 0:
        kwargs["since"] = int(time.time()) - since_minutes * 60
    replies = store.get_replies(**kwargs)
    if not replies:
        return "No replies found"
    lines = [f"{m.from_user}: {m.content}" for m in replies]
    return f"Replies ({len(replies)}):\n" + "\n".join(lines)


def _build_health_handler() -> Callable[[Request], Awaitable[Response]]:
    async def health(request: Request) -> JSONResponse:
        _ = request
        return JSONResponse({"status": "ok"})

    return health


def _build_callback_handler(store) -> Callable[[Request], Awaitable[Response]]:
    async def callback(request: Request) -> Response:
        token = os.environ.get("WECOM_CALLBACK_TOKEN", "")
        encoding_aes_key = os.environ.get("WECOM_CALLBACK_ENCODING_AES_KEY", "")
        corp_id = os.environ.get("WECOM_CORP_ID", "")

        signature = request.query_params.get("msg_signature", "")
        timestamp = request.query_params.get("timestamp", "")
        nonce = request.query_params.get("nonce", "")

        if request.method == "GET":
            echostr = request.query_params.get("echostr", "")
            if not verify_signature(token, timestamp, nonce, echostr, signature):
                return PlainTextResponse("invalid signature", status_code=403)
            try:
                plaintext, _ = decrypt_message(encoding_aes_key, echostr)
            except Exception:
                return PlainTextResponse("bad request", status_code=400)
            return PlainTextResponse(plaintext)

        body = await request.body()
        body_text = body.decode("utf-8")

        try:
            envelope = parse_callback_xml(body_text)
            encrypted = envelope.get("Encrypt", "")
        except Exception:
            return PlainTextResponse("bad request", status_code=400)

        if not verify_signature(token, timestamp, nonce, encrypted, signature):
            return PlainTextResponse("invalid signature", status_code=403)

        try:
            decrypted_xml, decrypted_corp_id = decrypt_message(encoding_aes_key, encrypted)
            if corp_id and decrypted_corp_id != corp_id:
                return PlainTextResponse("invalid corp id", status_code=403)

            message_data = parse_callback_xml(decrypted_xml)
            content = message_data.get("Content", "") or message_data.get("Event", "")
            store.save_message(
                WeComMessage(
                    msg_id=message_data.get("MsgId", ""),
                    msg_type=message_data.get("MsgType", ""),
                    from_user=message_data.get("FromUserName", ""),
                    to_user=message_data.get("ToUserName", ""),
                    content=content,
                    create_time=int(message_data.get("CreateTime", "0") or 0),
                    direction="received",
                )
            )
        except Exception:
            return PlainTextResponse("bad request", status_code=400)

        return PlainTextResponse("success")

    return callback


def _register_custom_route(
    mcp: FastMCP,
    path: str,
    methods: list[str],
    handler: Callable[[Request], Awaitable[Response]],
) -> None:
    custom_route = getattr(mcp, "custom_route", None)
    if callable(custom_route):
        custom_route(path, methods=methods)(handler)
        return

    routes = getattr(mcp, "_custom_starlette_routes", None)
    if routes is None:
        routes = []
        setattr(mcp, "_custom_starlette_routes", routes)
    routes.append(Route(path, endpoint=handler, methods=methods))


def create_mcp_server(client, store, *, host: str = "0.0.0.0", port: int = 8000) -> FastMCP:
    mcp = FastMCP("wecom-mcp", host=host, port=port)

    @mcp.tool()
    async def check_status() -> str:
        """Check WeCom API connection status"""
        return await check_status_handler(client, store)

    @mcp.tool()
    async def send_message(content: str, to: str = "@all") -> str:
        """Send message to user by name or @all"""
        return await send_message_handler(client, store, content=content, to=to)

    @mcp.tool()
    async def send_image(image_base64: str, filename: str = "image.png", to: str = "@all") -> str:
        """Send image (base64-encoded) to user by name or @all"""
        return await send_image_handler(client, store, image_base64=image_base64, filename=filename, to=to)

    @mcp.tool()
    async def list_users(department_id: int = 1) -> str:
        """List cached users from address book"""
        return await list_users_handler(client, store, department_id=department_id)

    @mcp.tool()
    async def get_messages(from_user: str = "", limit: int = 20, since_minutes: int = 0) -> str:
        """Get message history"""
        return await get_messages_handler(
            client,
            store,
            from_user=from_user,
            limit=limit,
            since_minutes=since_minutes,
        )

    @mcp.tool()
    async def get_replies(since_minutes: int = 60, limit: int = 50) -> str:
        """Get received replies"""
        return await get_replies_handler(client, store, since_minutes=since_minutes, limit=limit)

    _register_custom_route(mcp, "/health", ["GET"], _build_health_handler())
    _register_custom_route(mcp, "/callback", ["GET", "POST"], _build_callback_handler(store))

    return mcp


def main() -> None:
    corp_id = os.environ.get("WECOM_CORP_ID", "")
    agent_secret = os.environ.get("WECOM_AGENT_SECRET", "")
    agent_id = os.environ.get("WECOM_AGENT_ID", "")
    db_path = os.environ.get("WECOM_DB_PATH", "wecom.db")
    host = os.environ.get("WECOM_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("WECOM_MCP_PORT", "8000"))

    proxy_url = os.environ.get("WECOM_PROXY_URL", "")
    proxy_key = os.environ.get("WECOM_PROXY_KEY", "")
    extra: dict[str, str] = {}
    if proxy_key:
        extra["X-Proxy-Key"] = proxy_key

    client = WeComClient(
        corp_id,
        agent_secret,
        agent_id,
        **({"base_url": proxy_url} if proxy_url else {}),
        **({"extra_headers": extra} if extra else {}),
    )
    store = WeComStore(db_path)
    server = create_mcp_server(client, store, host=host, port=port)
    server.run(transport="streamable-http")


__all__ = [
    "create_mcp_server",
    "check_status_handler",
    "send_message_handler",
    "send_image_handler",
    "list_users_handler",
    "get_messages_handler",
    "get_replies_handler",
    "main",
]
