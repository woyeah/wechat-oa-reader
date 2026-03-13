#!/usr/bin/env python3
"""WeChat QR code login or manual credential input."""
import argparse
import asyncio
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from wechat_oa_reader.auth import login_with_qrcode, save_credentials
from wechat_oa_reader.models import Credentials


def main():
    parser = argparse.ArgumentParser(description="WeChat OA login")
    parser.add_argument("--manual", action="store_true", help="Manual credential input")
    parser.add_argument("--token", default="", help="WeChat token")
    parser.add_argument("--cookie", default="", help="WeChat cookie")
    parser.add_argument("--fakeid", default="", help="Account fakeid")
    parser.add_argument("--nickname", default="", help="Account nickname")
    args = parser.parse_args()

    if args.manual:
        if not args.token or not args.cookie:
            print(json.dumps({"success": False, "error": "--token and --cookie required for manual login"}))
            sys.exit(1)
        creds = Credentials(
            token=args.token,
            cookie=args.cookie,
            fakeid=args.fakeid or None,
            nickname=args.nickname or None,
        )
        save_credentials(creds)
        print(json.dumps({"success": True, "mode": "manual", "nickname": creds.nickname}))
        return

    try:
        creds = asyncio.run(login_with_qrcode())
        save_credentials(creds)
        print(json.dumps({
            "success": True,
            "mode": "qrcode",
            "nickname": creds.nickname,
            "fakeid": creds.fakeid,
        }, ensure_ascii=False))
    except TimeoutError:
        print(json.dumps({"success": False, "error": "QR code expired, please try again"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
