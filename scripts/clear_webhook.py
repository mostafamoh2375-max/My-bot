#!/usr/bin/env python3
"""
scripts/clear_webhook.py

One-off helper to delete Telegram webhook and show verification info.

Usage (recommended):
  export TELEGRAM_BOT_TOKEN="<YOUR_TOKEN>"
  python scripts/clear_webhook.py

Or pass the token on the command line (less secure):
  python scripts/clear_webhook.py --token "<YOUR_TOKEN>"

This script will:
  1) Call deleteWebhook?drop_pending_updates=true
  2) Call getWebhookInfo
  3) Call getMe

It prints the JSON responses for each call. Do NOT share the token or the token value publicly.
"""
import os
import sys
import argparse
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional

TIMEOUT = 10  # seconds


def call_telegram_api(method: str, token: str, params: Optional[dict] = None, timeout: int = TIMEOUT):
    base = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        qs = urllib.parse.urlencode(params)
        url = f"{base}?{qs}"
    else:
        url = base
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as he:
        try:
            body = he.read().decode("utf-8")
            return {"ok": False, "http_error": str(he), "body": body}
        except Exception:
            return {"ok": False, "http_error": str(he)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def pretty_print(title: str, obj):
    print("=" * 80)
    print(title)
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Delete Telegram webhook and show verification info.")
    parser.add_argument("--token", "-t", help="Telegram bot token (optional; prefer env var TELEGRAM_BOT_TOKEN)")
    args = parser.parse_args()

    token = args.token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not provided. Set env var or pass --token.", file=sys.stderr)
        sys.exit(2)

    print("Deleting webhook (drop_pending_updates=true)...")
    res_del = call_telegram_api("deleteWebhook", token, params={"drop_pending_updates": "true"})
    pretty_print("deleteWebhook response", res_del)

    print("Fetching getWebhookInfo to confirm status...")
    res_info = call_telegram_api("getWebhookInfo", token)
    pretty_print("getWebhookInfo response", res_info)

    print("Fetching getMe to confirm bot identity...")
    res_me = call_telegram_api("getMe", token)
    pretty_print("getMe response", res_me)

    # Decide exit code
    if isinstance(res_del, dict) and res_del.get("ok"):
        print("Webhook deletion reported OK.")
        sys.exit(0)
    else:
        print("Webhook deletion reported failure (see above).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
