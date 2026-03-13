#!/usr/bin/env python3
"""Check if wechat-oa-reader is installed, auto-install if not."""
import json
import subprocess
import sys


def main():
    try:
        import wechat_oa_reader  # noqa: F401
        print(json.dumps({"installed": True, "version": wechat_oa_reader.__version__}))
    except ImportError:
        print("wechat-oa-reader not found, installing...", file=sys.stderr)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "wechat-oa-reader"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(json.dumps({"installed": False, "error": result.stderr.strip()}))
            sys.exit(1)
        import wechat_oa_reader  # noqa: F401
        print(json.dumps({"installed": True, "version": wechat_oa_reader.__version__}))


if __name__ == "__main__":
    main()
