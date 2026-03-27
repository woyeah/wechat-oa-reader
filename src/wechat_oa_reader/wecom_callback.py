# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from .models import WeComMessage, WeComUser
from .wecom_crypto import decrypt_message, parse_callback_xml, verify_signature
from .wecom_store import WeComStore


class WeComCallbackServer:
    def __init__(
        self,
        host: str,
        port: int,
        token: str,
        encoding_aes_key: str,
        corp_id: str,
        store: WeComStore,
        wecom_client: object | None = None,
    ):
        self.host = host
        self.token = token
        self.encoding_aes_key = encoding_aes_key
        self.corp_id = corp_id
        self.store = store
        self.wecom_client = wecom_client
        self._thread: threading.Thread | None = None

        parent = self

        class Handler(BaseHTTPRequestHandler):
            def _query_params(self) -> dict[str, str]:
                query = parse_qs(urlparse(self.path).query)
                return {k: v[0] for k, v in query.items() if v}

            def _write_response(self, status: int, body: str = "") -> None:
                payload = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if payload:
                    self.wfile.write(payload)

            def _sync_get_user(self, userid: str) -> WeComUser | None:
                client = parent.wecom_client
                if client is None:
                    return None
                get_user = getattr(client, "get_user", None)
                if get_user is None:
                    return None
                result = get_user(userid)
                if asyncio.iscoroutine(result):
                    return asyncio.run(result)
                return result

            def do_GET(self) -> None:  # noqa: N802
                params = self._query_params()
                signature = params.get("msg_signature", "")
                timestamp = params.get("timestamp", "")
                nonce = params.get("nonce", "")
                echostr = params.get("echostr", "")

                if not verify_signature(parent.token, timestamp, nonce, echostr, signature):
                    self._write_response(403)
                    return

                try:
                    plaintext, _ = decrypt_message(parent.encoding_aes_key, echostr)
                except Exception:
                    self._write_response(400)
                    return
                self._write_response(200, plaintext)

            def do_POST(self) -> None:  # noqa: N802
                params = self._query_params()
                signature = params.get("msg_signature", "")
                timestamp = params.get("timestamp", "")
                nonce = params.get("nonce", "")

                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length).decode("utf-8")

                try:
                    envelope = parse_callback_xml(body)
                    encrypted = envelope.get("Encrypt", "")
                except Exception:
                    self._write_response(400)
                    return

                if not verify_signature(parent.token, timestamp, nonce, encrypted, signature):
                    self._write_response(403)
                    return

                try:
                    decrypted_xml, decrypted_corp_id = decrypt_message(parent.encoding_aes_key, encrypted)
                    if decrypted_corp_id != parent.corp_id:
                        self._write_response(403)
                        return
                    message_data = parse_callback_xml(decrypted_xml)
                    msg = WeComMessage(
                        msg_id=message_data.get("MsgId", ""),
                        msg_type=message_data.get("MsgType", ""),
                        from_user=message_data.get("FromUserName", ""),
                        to_user=message_data.get("ToUserName", ""),
                        content=message_data.get("Content", ""),
                        create_time=int(message_data.get("CreateTime", "0") or 0),
                        direction="received",
                    )
                    parent.store.save_message(msg)
                    if parent.wecom_client is not None and msg.from_user:
                        try:
                            user = self._sync_get_user(msg.from_user)
                            if user is not None:
                                parent.store.save_user(user)
                        except Exception:
                            pass
                except Exception:
                    self._write_response(400)
                    return

                self._write_response(200)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        self._httpd = HTTPServer((host, port), Handler)

    @property
    def port(self) -> int:
        return int(self._httpd.server_port)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
