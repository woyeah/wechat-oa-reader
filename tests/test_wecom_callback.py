# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import base64
import hashlib
import http.client
import shutil
import struct
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from wechat_oa_reader.wecom_callback import WeComCallbackServer
from wechat_oa_reader.wecom_store import WeComStore

TOKEN = "test_token_123"
ENCODING_AES_KEY = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
CORP_ID = "wx12345678"


def _compute_signature(token: str, timestamp: str, nonce: str, encrypted_msg: str) -> str:
    items = sorted([token, timestamp, nonce, encrypted_msg])
    return hashlib.sha1("".join(items).encode("utf-8")).hexdigest()


def _aes_key_from_encoding_key(encoding_aes_key: str) -> bytes:
    return base64.b64decode(f"{encoding_aes_key}=")


def _pkcs7_pad(data: bytes, block_size: int = 32) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    if pad_len == 0:
        pad_len = block_size
    return data + bytes([pad_len]) * pad_len


def _encrypt_for_test(encoding_aes_key: str, msg: str, corp_id: str) -> str:
    aes_key = _aes_key_from_encoding_key(encoding_aes_key)
    iv = aes_key[:16]
    msg_bytes = msg.encode("utf-8")
    corp_bytes = corp_id.encode("utf-8")
    plaintext = b"R" * 16 + struct.pack("!I", len(msg_bytes)) + msg_bytes + corp_bytes
    padded = _pkcs7_pad(plaintext, block_size=32)
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("utf-8")


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
def callback_server(tmp_path: Path) -> Iterator[tuple[WeComCallbackServer, int, WeComStore]]:
    store = WeComStore(str(tmp_path / "wecom.db"))
    server = WeComCallbackServer(
        host="127.0.0.1",
        port=0,
        token=TOKEN,
        encoding_aes_key=ENCODING_AES_KEY,
        corp_id=CORP_ID,
        store=store,
        wecom_client=None,
    )
    server.start()
    try:
        yield server, server.port, store
    finally:
        server.shutdown()


def _http_get(host: str, port: int, path: str) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def _http_post(host: str, port: int, path: str, body: str) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request(
            "POST",
            path,
            body=body.encode("utf-8"),
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


class TestCallbackServerVerification:
    def test_get_url_verification(self, callback_server: tuple[WeComCallbackServer, int, WeComStore]) -> None:
        _, port, _ = callback_server
        timestamp = "1710000000"
        nonce = "nonce-abc"
        expected_plaintext = "verify-ok"
        echostr = _encrypt_for_test(ENCODING_AES_KEY, expected_plaintext, CORP_ID)
        signature = _compute_signature(TOKEN, timestamp, nonce, echostr)

        status, body = _http_get(
            "127.0.0.1",
            port,
            f"/callback?msg_signature={signature}&timestamp={timestamp}&nonce={nonce}&echostr={echostr}",
        )

        assert status == 200
        assert body.decode("utf-8") == expected_plaintext

    def test_get_invalid_signature(self, callback_server: tuple[WeComCallbackServer, int, WeComStore]) -> None:
        _, port, _ = callback_server
        timestamp = "1710000000"
        nonce = "nonce-abc"
        echostr = _encrypt_for_test(ENCODING_AES_KEY, "verify-ok", CORP_ID)

        status, _ = _http_get(
            "127.0.0.1",
            port,
            f"/callback?msg_signature=bad-signature&timestamp={timestamp}&nonce={nonce}&echostr={echostr}",
        )

        assert status == 403


class TestCallbackServerMessage:
    def test_post_text_message(self, callback_server: tuple[WeComCallbackServer, int, WeComStore]) -> None:
        _, port, store = callback_server
        timestamp = "1710000000"
        nonce = "nonce-abc"

        inner_xml = (
            "<xml>"
            "<ToUserName><![CDATA[wx12345678]]></ToUserName>"
            "<FromUserName><![CDATA[zhangsan]]></FromUserName>"
            "<CreateTime>1348831860</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[hello]]></Content>"
            "<MsgId>123456</MsgId>"
            "<AgentID>1000001</AgentID>"
            "</xml>"
        )
        encrypted_b64 = _encrypt_for_test(ENCODING_AES_KEY, inner_xml, CORP_ID)
        envelope_xml = (
            "<xml>"
            "<ToUserName><![CDATA[wx12345678]]></ToUserName>"
            f"<Encrypt><![CDATA[{encrypted_b64}]]></Encrypt>"
            "<AgentID><![CDATA[1000001]]></AgentID>"
            "</xml>"
        )
        signature = _compute_signature(TOKEN, timestamp, nonce, encrypted_b64)

        status, body = _http_post(
            "127.0.0.1",
            port,
            f"/callback?msg_signature={signature}&timestamp={timestamp}&nonce={nonce}",
            envelope_xml,
        )

        assert status == 200
        assert body == b""
        messages = store.get_messages(limit=10)
        assert len(messages) == 1
        msg = messages[0]
        assert msg.msg_id == "123456"
        assert msg.msg_type == "text"
        assert msg.from_user == "zhangsan"
        assert msg.to_user == "wx12345678"
        assert msg.content == "hello"
        assert msg.create_time == 1348831860
        assert msg.direction == "received"

    def test_post_invalid_signature(self, callback_server: tuple[WeComCallbackServer, int, WeComStore]) -> None:
        _, port, _ = callback_server
        timestamp = "1710000000"
        nonce = "nonce-abc"

        inner_xml = (
            "<xml>"
            "<ToUserName><![CDATA[wx12345678]]></ToUserName>"
            "<FromUserName><![CDATA[zhangsan]]></FromUserName>"
            "<CreateTime>1348831860</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[hello]]></Content>"
            "<MsgId>123456</MsgId>"
            "<AgentID>1000001</AgentID>"
            "</xml>"
        )
        encrypted_b64 = _encrypt_for_test(ENCODING_AES_KEY, inner_xml, CORP_ID)
        envelope_xml = (
            "<xml>"
            "<ToUserName><![CDATA[wx12345678]]></ToUserName>"
            f"<Encrypt><![CDATA[{encrypted_b64}]]></Encrypt>"
            "<AgentID><![CDATA[1000001]]></AgentID>"
            "</xml>"
        )

        status, _ = _http_post(
            "127.0.0.1",
            port,
            f"/callback?msg_signature=bad-signature&timestamp={timestamp}&nonce={nonce}",
            envelope_xml,
        )

        assert status == 403
