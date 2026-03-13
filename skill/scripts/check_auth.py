#!/usr/bin/env python3
"""Check WeChat credential status."""
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from wechat_oa_reader.auth import load_credentials


def main():
    creds = load_credentials()
    if not creds:
        print(json.dumps({"status": "missing"}, ensure_ascii=False))
        return

    now_ms = int(time.time() * 1000)
    expire = creds.expire_time or 0

    if expire > 0 and now_ms > expire:
        print(json.dumps({
            "status": "expired",
            "nickname": creds.nickname,
            "fakeid": creds.fakeid,
        }, ensure_ascii=False))
        return

    remaining_hours = round((expire - now_ms) / 3600000, 1) if expire > 0 else None
    print(json.dumps({
        "status": "valid",
        "nickname": creds.nickname,
        "fakeid": creds.fakeid,
        "remaining_hours": remaining_hours,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
