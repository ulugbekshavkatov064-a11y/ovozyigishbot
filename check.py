"""Telegram ulanishini tekshirish: python check.py"""
import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()
token = os.getenv("BOT_TOKEN", "").strip()
print("Token uzunligi:", len(token), "| boshlanishi:", token.split(":")[0] if ":" in token else "NOTO'G'RI FORMAT")
print("Tizim proksisi:", urllib.request.getproxies() or "yo'q")

for method in ("getMe", "getWebhookInfo"):
    url = f"https://api.telegram.org/bot{token}/{method}"
    t = time.time()
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            body = r.read().decode()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
    except Exception as e:  # noqa: BLE001
        body = f"XATO: {e!r}"
    print(f"\n{method} ({time.time() - t:.1f} s):")
    try:
        print(json.dumps(json.loads(body), ensure_ascii=False, indent=2))
    except ValueError:
        print(body)
