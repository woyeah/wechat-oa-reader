# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import base64
import hashlib
import struct

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from wechat_oa_reader.wecom_crypto import (
    decrypt_message,
    encrypt_message,
    parse_callback_xml,
    verify_signature,
)

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


class TestVerifySignature:
    def test_valid_signature(self) -> None:
        timestamp = "1710000000"
        nonce = "nonce-abc"
        encrypted_msg = "encrypted-payload"
        signature = _compute_signature(TOKEN, timestamp, nonce, encrypted_msg)
        assert verify_signature(TOKEN, timestamp, nonce, encrypted_msg, signature)

    def test_invalid_signature(self) -> None:
        assert not verify_signature(TOKEN, "1710000000", "nonce-abc", "encrypted-payload", "bad-signature")

    def test_empty_values(self) -> None:
        signature = _compute_signature("", "", "", "")
        assert verify_signature("", "", "", "", signature)


class TestDecryptMessage:
    def test_decrypt_roundtrip(self) -> None:
        encrypted = _encrypt_for_test(ENCODING_AES_KEY, "hello wecom", CORP_ID)
        msg, corp_id = decrypt_message(ENCODING_AES_KEY, encrypted)
        assert msg == "hello wecom"
        assert corp_id == CORP_ID

    def test_unicode_message(self) -> None:
        encrypted = _encrypt_for_test(ENCODING_AES_KEY, "你好，企业微信🚀", CORP_ID)
        msg, corp_id = decrypt_message(ENCODING_AES_KEY, encrypted)
        assert msg == "你好，企业微信🚀"
        assert corp_id == CORP_ID

    def test_invalid_key_raises_exception(self) -> None:
        encrypted = _encrypt_for_test(ENCODING_AES_KEY, "hello wecom", CORP_ID)
        with pytest.raises(Exception):
            decrypt_message("short-key", encrypted)


class TestEncryptMessage:
    def test_encrypt_xml_contains_required_tags(self) -> None:
        nonce = "nonce-xyz"
        timestamp = "1710000001"
        xml = encrypt_message(
            ENCODING_AES_KEY,
            "<xml><Content>reply</Content></xml>",
            CORP_ID,
            nonce,
            token=TOKEN,
            timestamp=timestamp,
        )
        assert "<Encrypt>" in xml
        assert "<MsgSignature>" in xml
        assert "<TimeStamp>" in xml
        assert "<Nonce>" in xml


class TestParseCallbackXml:
    def test_parse_text_message_xml(self) -> None:
        xml = """
<xml>
  <ToUserName><![CDATA[to_user]]></ToUserName>
  <FromUserName><![CDATA[from_user]]></FromUserName>
  <CreateTime>1710000000</CreateTime>
  <MsgType><![CDATA[text]]></MsgType>
  <Content><![CDATA[hello]]></Content>
  <MsgId>1234567890</MsgId>
  <AgentID>1000002</AgentID>
</xml>
"""
        parsed = parse_callback_xml(xml)
        assert parsed["ToUserName"] == "to_user"
        assert parsed["FromUserName"] == "from_user"
        assert parsed["CreateTime"] == "1710000000"
        assert parsed["MsgType"] == "text"
        assert parsed["Content"] == "hello"
        assert parsed["MsgId"] == "1234567890"
        assert parsed["AgentID"] == "1000002"

    def test_parse_empty_xml(self) -> None:
        assert parse_callback_xml("<xml></xml>") == {}

    def test_parse_encrypted_envelope_xml(self) -> None:
        xml = """
<xml>
  <ToUserName><![CDATA[corp_target]]></ToUserName>
  <Encrypt><![CDATA[encrypted_payload_base64]]></Encrypt>
  <AgentID>1000002</AgentID>
</xml>
"""
        parsed = parse_callback_xml(xml)
        assert parsed["ToUserName"] == "corp_target"
        assert parsed["Encrypt"] == "encrypted_payload_base64"
        assert parsed["AgentID"] == "1000002"
