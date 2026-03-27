# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import base64
import hashlib
import os
import struct
import time

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from defusedxml import ElementTree


def _decode_aes_key(encoding_aes_key: str) -> bytes:
    aes_key = base64.b64decode(f"{encoding_aes_key}=")
    if len(aes_key) != 32:
        raise ValueError("Invalid AES key length")
    return aes_key


def _pkcs7_pad(data: bytes, block_size: int = 32) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    if pad_len == 0:
        pad_len = block_size
    return data + bytes([pad_len]) * pad_len


def _pkcs7_unpad(data: bytes, block_size: int = 32) -> bytes:
    if not data:
        raise ValueError("Invalid padded data")
    pad_len = data[-1]
    if pad_len < 1 or pad_len > block_size:
        raise ValueError("Invalid PKCS7 padding")
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        raise ValueError("Invalid PKCS7 padding")
    return data[:-pad_len]


def verify_signature(token: str, timestamp: str, nonce: str, encrypted_msg: str, signature: str) -> bool:
    items = sorted([token, timestamp, nonce, encrypted_msg])
    expected = hashlib.sha1("".join(items).encode("utf-8")).hexdigest()
    return expected == signature


def decrypt_message(encoding_aes_key: str, encrypted_msg: str) -> tuple[str, str]:
    aes_key = _decode_aes_key(encoding_aes_key)
    iv = aes_key[:16]
    encrypted_bytes = base64.b64decode(encrypted_msg)

    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded_plaintext = decryptor.update(encrypted_bytes) + decryptor.finalize()
    plaintext = _pkcs7_unpad(padded_plaintext, block_size=32)

    if len(plaintext) < 20:
        raise ValueError("Decrypted message too short")

    content = plaintext[16:]
    msg_len = struct.unpack("!I", content[:4])[0]
    msg_bytes = content[4 : 4 + msg_len]
    corp_id_bytes = content[4 + msg_len :]

    return msg_bytes.decode("utf-8"), corp_id_bytes.decode("utf-8")


def encrypt_message(
    encoding_aes_key: str,
    reply_xml: str,
    corp_id: str,
    nonce: str,
    *,
    token: str = "",
    timestamp: str | None = None,
) -> str:
    if timestamp is None:
        timestamp = str(int(time.time()))

    aes_key = _decode_aes_key(encoding_aes_key)
    iv = aes_key[:16]
    msg_bytes = reply_xml.encode("utf-8")
    corp_id_bytes = corp_id.encode("utf-8")

    plaintext = os.urandom(16) + struct.pack("!I", len(msg_bytes)) + msg_bytes + corp_id_bytes
    padded = _pkcs7_pad(plaintext, block_size=32)

    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

    signature = hashlib.sha1("".join(sorted([token, timestamp, nonce, encrypted_b64])).encode("utf-8")).hexdigest()

    return (
        "<xml>"
        f"<Encrypt><![CDATA[{encrypted_b64}]]></Encrypt>"
        f"<MsgSignature><![CDATA[{signature}]]></MsgSignature>"
        f"<TimeStamp>{timestamp}</TimeStamp>"
        f"<Nonce><![CDATA[{nonce}]]></Nonce>"
        "</xml>"
    )


def parse_callback_xml(xml_str: str) -> dict[str, str]:
    root = ElementTree.fromstring(xml_str)
    data: dict[str, str] = {}
    for child in root:
        data[child.tag] = child.text or ""
    return data
