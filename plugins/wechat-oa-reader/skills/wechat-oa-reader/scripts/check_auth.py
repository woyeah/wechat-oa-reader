#!/usr/bin/env python3
"""Check WeChat credential status."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))
sys.modules.pop("_errors", None)

from wechat_oa_reader.auth import load_credentials
from wechat_oa_reader.client import WeChatClient

from _errors import classify_error


def main():
    try:
        creds = load_credentials()
        if not creds:
            print(json.dumps({"status": "missing"}, ensure_ascii=False))
            return

        now_ms = int(time.time() * 1000)
        expire = creds.expire_time or 0

        if expire > 0 and now_ms > expire:
            print(
                json.dumps(
                    {
                        "status": "expired",
                        "nickname": creds.nickname,
                        "fakeid": creds.fakeid,
                        "reason": "local_expire_time",
                    },
                    ensure_ascii=False,
                )
            )
            return

        client = asyncio.run(WeChatClient.from_credentials(creds))
        is_valid = asyncio.run(client.check_auth())

        if is_valid:
            remaining_hours = round((expire - now_ms) / 3600000, 1) if expire > 0 else None
            print(
                json.dumps(
                    {
                        "status": "valid",
                        "nickname": creds.nickname,
                        "fakeid": creds.fakeid,
                        "remaining_hours": remaining_hours,
                    },
                    ensure_ascii=False,
                )
            )
            return

        print(
            json.dumps(
                {
                    "status": "expired",
                    "nickname": creds.nickname,
                    "fakeid": creds.fakeid,
                    "reason": "server_rejected",
                },
                ensure_ascii=False,
            )
        )
    except Exception as e:
        print(json.dumps(classify_error(e), ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
