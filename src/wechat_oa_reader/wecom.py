# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import time

import httpx


class WeComClient:
    def __init__(self, corp_id: str, agent_secret: str, agent_id: str | int):
        self._corp_id = corp_id
        self._agent_secret = agent_secret
        self._agent_id = agent_id
        self._cached_token: str | None = None
        self._token_expires_at: float = 0.0

    async def get_access_token(self) -> str:
        if self._cached_token is not None and time.time() < self._token_expires_at:
            return self._cached_token

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
                params={"corpid": self._corp_id, "corpsecret": self._agent_secret},
            )
            data = response.json()

        if data.get("errcode") != 0:
            raise RuntimeError(str(data.get("errmsg", "Unknown error")))

        access_token = data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise RuntimeError("Missing access_token in WeCom response")

        expires_in = data.get("expires_in", 0)
        self._cached_token = access_token
        self._token_expires_at = time.time() + float(expires_in) - 60
        return access_token

    async def send_text(self, content: str, to_user: str = "@all") -> dict:
        token = await self.get_access_token()
        payload = {
            "touser": to_user,
            "msgtype": "text",
            "agentid": self._agent_id,
            "text": {"content": content},
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}",
                json=payload,
            )
            data = response.json()

        if data.get("errcode") != 0:
            raise RuntimeError(str(data.get("errmsg", "Unknown error")))
        return data

    async def upload_media(self, data: bytes, filename: str, media_type: str = "image") -> str:
        """Upload media to WeCom and return media_id."""
        token = await self.get_access_token()
        url = (
            "https://qyapi.weixin.qq.com/cgi-bin/media/upload"
            f"?access_token={token}&type={media_type}"
        )
        files = {"media": (filename, data)}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, files=files)
            result = response.json()
        if result.get("errcode") != 0:
            raise RuntimeError(str(result.get("errmsg", "Unknown error")))
        media_id = result.get("media_id")
        if not media_id:
            raise RuntimeError("Missing media_id in WeCom response")
        return media_id

    async def send_image(self, media_id: str, to_user: str = "@all") -> dict:
        """Send an image message via WeCom."""
        token = await self.get_access_token()
        payload = {
            "touser": to_user,
            "msgtype": "image",
            "agentid": self._agent_id,
            "image": {"media_id": media_id},
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}",
                json=payload,
            )
            result = response.json()
        if result.get("errcode") != 0:
            raise RuntimeError(str(result.get("errmsg", "Unknown error")))
        return result
