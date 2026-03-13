#!/usr/bin/env python3
"""WeChat QR code login or manual credential input."""
import argparse
import asyncio
import io
import json
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
import os
sys.path.insert(0, os.path.dirname(__file__))
from _errors import classify_error

from wechat_oa_reader.auth import (
    login_with_qrcode,
    start_qrcode_login,
    complete_qrcode_login,
    save_credentials,
)
from wechat_oa_reader.models import Credentials


def _print_qr_ascii(png_bytes: bytes) -> None:
    try:
        from PIL import Image
    except Exception:
        print("Install Pillow to see QR code in terminal")
        return

    try:
        image = Image.open(io.BytesIO(png_bytes)).convert("L")
    except Exception:
        return
    size = min(image.size[0], image.size[1], 41)
    resample = getattr(Image, "Resampling", Image).NEAREST
    image = image.resize((size, size), resample)

    matrix = [
        [image.getpixel((x, y)) < 128 for x in range(size)]
        for y in range(size)
    ]

    bordered_size = size + 2
    bordered = [[False] * bordered_size]
    for row in matrix:
        bordered.append([False] + row + [False])
    bordered.append([False] * bordered_size)

    if len(bordered) % 2 == 1:
        bordered.append([False] * bordered_size)

    print("--- Scan QR Code ---")
    for y in range(0, len(bordered), 2):
        top = bordered[y]
        bottom = bordered[y + 1]
        line_chars = []
        for x in range(bordered_size):
            top_dark = top[x]
            bottom_dark = bottom[x]
            if top_dark and bottom_dark:
                line_chars.append("█")
            elif top_dark and not bottom_dark:
                line_chars.append("▀")
            elif not top_dark and bottom_dark:
                line_chars.append("▄")
            else:
                line_chars.append(" ")
        print("".join(line_chars))
    print("--- Scan QR Code ---")


def _open_image(path: str) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="WeChat OA login")
    parser.add_argument("--manual", action="store_true", help="Manual credential input")
    parser.add_argument("--token", default="", help="WeChat token")
    parser.add_argument("--cookie", default="", help="WeChat cookie")
    parser.add_argument("--fakeid", default="", help="Account fakeid")
    parser.add_argument("--nickname", default="", help="Account nickname")
    parser.add_argument("--start", action="store_true", help="Phase 1: get QR code only")
    parser.add_argument("--complete", action="store_true", help="Phase 2: complete login")
    parser.add_argument("--session", default="", help="Session file path for --complete")
    args = parser.parse_args(argv)

    if args.start:
        try:
            qr_bytes, session_path = asyncio.run(start_qrcode_login())
            _print_qr_ascii(qr_bytes)
            with tempfile.NamedTemporaryFile(prefix="wechat-oa-", suffix=".png", delete=False) as f:
                f.write(qr_bytes)
                qr_path = f.name
            _open_image(qr_path)
            print(json.dumps({
                "phase": "start",
                "qr_path": qr_path,
                "session_path": session_path,
            }))
        except Exception as e:
            err = classify_error(e)
            print(json.dumps({"success": False, **err}))
            sys.exit(1)
        return

    if args.complete:
        if not args.session:
            print(json.dumps({
                "success": False,
                "error": "--session required for --complete mode",
                "error_code": "invalid_input",
            }))
            sys.exit(1)
        try:
            creds = asyncio.run(complete_qrcode_login(args.session))
            save_credentials(creds)
            print(json.dumps({
                "success": True,
                "mode": "qrcode",
                "nickname": creds.nickname,
                "fakeid": creds.fakeid,
            }, ensure_ascii=False))
        except TimeoutError:
            print(json.dumps({
                "success": False,
                "error": "QR code expired, please try again",
                "error_code": "auth_timeout",
            }))
            sys.exit(1)
        except Exception as e:
            err = classify_error(e)
            print(json.dumps({"success": False, **err}))
            sys.exit(1)
        return

    if args.manual:
        if not args.token or not args.cookie:
            print(json.dumps({
                "success": False,
                "error": "--token and --cookie required for manual login",
                "error_code": "invalid_input",
            }))
            sys.exit(1)
        creds = Credentials(
            token=args.token,
            cookie=args.cookie,
            fakeid=args.fakeid or None,
            nickname=args.nickname or None,
        )
        save_credentials(creds)
        warning = None
        try:
            from wechat_oa_reader.client import WeChatClient
            client = WeChatClient(token=creds.token, cookie=creds.cookie)
            asyncio.run(client.search_accounts("test", count=1))
        except Exception as ve:
            warning = f"Credentials saved but validation failed: {ve}"

        result = {"success": True, "mode": "manual", "nickname": creds.nickname}
        if warning:
            result["warning"] = warning
        print(json.dumps(result, ensure_ascii=False))
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
        print(json.dumps({
            "success": False,
            "error": "QR code expired, please try again",
            "error_code": "auth_timeout",
        }))
        sys.exit(1)
    except Exception as e:
        err = classify_error(e)
        print(json.dumps({"success": False, **err}))
        sys.exit(1)


if __name__ == "__main__":
    main()
