# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import parse_qs, urlparse

import httpx
from dotenv import load_dotenv, set_key

from .models import Credentials

MP_BASE_URL = "https://mp.weixin.qq.com"


async def start_qrcode_login() -> tuple[bytes, str]:
    """Phase 1: start login and get QR code.

    Returns (qr_png_bytes, session_file_path).
    """
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://mp.weixin.qq.com/",
            "Origin": "https://mp.weixin.qq.com",
        }

        await client.post(
            f"{MP_BASE_URL}/cgi-bin/bizlogin",
            params={"action": "startlogin"},
            data={
                "userlang": "zh_CN",
                "redirect_url": "",
                "login_type": 3,
                "sessionid": str(int(time.time() * 1000)),
                "token": "",
                "lang": "zh_CN",
                "f": "json",
                "ajax": 1,
            },
            headers=headers,
        )

        qr_resp = await client.get(
            f"{MP_BASE_URL}/cgi-bin/scanloginqrcode",
            params={"action": "getqrcode", "random": int(time.time() * 1000)},
            headers=headers,
        )
        qr_resp.raise_for_status()
        qr_bytes = qr_resp.content

        cookies_dict = {k: v for k, v in client.cookies.items()}
        session_file = tempfile.NamedTemporaryFile(
            prefix="wechat-session-", suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        json.dump({"cookies": cookies_dict}, session_file)
        session_file.close()

        return qr_bytes, session_file.name


async def complete_qrcode_login(session_path: str) -> Credentials:
    """Phase 2: poll for scan and complete login.

    Loads cookies from session file, returns Credentials.
    Deletes session file after use.
    """
    with open(session_path, encoding="utf-8") as f:
        session_data = json.load(f)
    cookies = session_data["cookies"]

    try:
        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, cookies=cookies
        ) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://mp.weixin.qq.com/",
                "Origin": "https://mp.weixin.qq.com",
            }

            while True:
                ask_resp = await client.get(
                    f"{MP_BASE_URL}/cgi-bin/scanloginqrcode",
                    params={"action": "ask", "token": "", "lang": "zh_CN", "f": "json", "ajax": 1},
                    headers=headers,
                )
                ask_resp.raise_for_status()
                data = ask_resp.json()
                status = data.get("status", 0)
                if status == 1:
                    break
                if status == 2:
                    raise TimeoutError("QR code expired")
                if status not in (0, 4, 6):
                    raise RuntimeError(f"Unexpected QR status: {status}")
                await asyncio.sleep(2)

            login_resp = await client.post(
                f"{MP_BASE_URL}/cgi-bin/bizlogin",
                params={"action": "login"},
                data={
                    "userlang": "zh_CN",
                    "redirect_url": "",
                    "cookie_forbidden": 0,
                    "cookie_cleaned": 0,
                    "plugin_used": 0,
                    "login_type": 3,
                    "token": "",
                    "lang": "zh_CN",
                    "f": "json",
                    "ajax": 1,
                },
                headers=headers,
            )
            login_resp.raise_for_status()
            result = login_resp.json()
            redirect_url = result.get("redirect_url", "")
            token = parse_qs(urlparse(f"http://localhost{redirect_url}").query).get("token", [""])[0]
            if not token:
                raise RuntimeError("Could not extract token from login response")

            cookie_str = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])

            home_resp = await client.get(
                f"{MP_BASE_URL}/cgi-bin/home",
                params={"t": "home/index", "token": token, "lang": "zh_CN"},
                headers={**headers, "Cookie": cookie_str},
            )
            home_resp.raise_for_status()

            nickname = ""
            nick_match = re.search(r"nick_name\s*[:=]\s*[\"']([^\"']+)[\"']", home_resp.text)
            if nick_match:
                nickname = nick_match.group(1)

            fakeid = ""
            if nickname:
                search_resp = await client.get(
                    f"{MP_BASE_URL}/cgi-bin/searchbiz",
                    params={
                        "action": "search_biz",
                        "token": token,
                        "lang": "zh_CN",
                        "f": "json",
                        "ajax": 1,
                        "query": nickname,
                        "begin": 0,
                        "count": 5,
                    },
                    headers={**headers, "Cookie": cookie_str},
                )
                search_resp.raise_for_status()
                search_result = search_resp.json()
                for account in search_result.get("list", []):
                    if account.get("nickname") == nickname:
                        fakeid = account.get("fakeid", "")
                        break
                if not fakeid and search_result.get("list"):
                    fakeid = search_result["list"][0].get("fakeid", "")

            return Credentials(
                token=token,
                cookie=cookie_str,
                fakeid=fakeid or None,
                nickname=nickname or None,
                expire_time=int((time.time() + 4 * 24 * 3600) * 1000),
            )
    finally:
        Path(session_path).unlink(missing_ok=True)


async def login_with_qrcode(
    on_qrcode: Callable[[bytes], Awaitable[None]] | None = None,
) -> Credentials:
    qr_bytes, session_path = await start_qrcode_login()
    if on_qrcode:
        await on_qrcode(qr_bytes)
    else:
        with tempfile.NamedTemporaryFile(prefix="wechat-oa-", suffix=".png", delete=False) as f:
            f.write(qr_bytes)
            print(f"QR code saved to: {f.name}")
    return await complete_qrcode_login(session_path)


def save_credentials(credentials: Credentials, path: Path | None = None) -> None:
    env_path = path or Path.cwd() / ".env"
    if not env_path.exists():
        env_path.touch()
    set_key(str(env_path), "WECHAT_TOKEN", credentials.token)
    set_key(str(env_path), "WECHAT_COOKIE", credentials.cookie)
    set_key(str(env_path), "WECHAT_FAKEID", credentials.fakeid or "")
    set_key(str(env_path), "WECHAT_NICKNAME", credentials.nickname or "")
    set_key(str(env_path), "WECHAT_EXPIRE_TIME", str(credentials.expire_time or 0))


def load_credentials(path: Path | None = None) -> Credentials | None:
    env_path = path or Path.cwd() / ".env"
    if not env_path.exists():
        return None

    load_dotenv(env_path, override=True)
    token = os.getenv("WECHAT_TOKEN", "")
    cookie = os.getenv("WECHAT_COOKIE", "")
    if not token or not cookie:
        return None

    expire_raw = os.getenv("WECHAT_EXPIRE_TIME") or "0"
    try:
        expire_time = int(expire_raw) or None
    except ValueError:
        expire_time = None

    return Credentials(
        token=token,
        cookie=cookie,
        fakeid=os.getenv("WECHAT_FAKEID") or None,
        nickname=os.getenv("WECHAT_NICKNAME") or None,
        expire_time=expire_time,
    )
