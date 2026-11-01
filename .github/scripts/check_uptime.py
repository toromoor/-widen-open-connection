#!/usr/bin/env python3
"""Independent WIDEN read-only uptime check. No secret keys needed."""
import json
import sys
import time
from urllib.request import Request, urlopen

BASE = "https://widen-night-souk-preview.onrender.com"


def check():
    req = Request(
        BASE + "/health",
        headers={"User-Agent": "WIDEN-Health-Check/1.0", "Accept": "application/json"},
    )
    with urlopen(req, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        health = json.load(response)
        if health.get("ok") is not True:
            raise RuntimeError("Health endpoint did not report ok")
        if health.get("writing") != "off" or health.get("mode") != "read-only-preview":
            raise RuntimeError("Unexpected read-only status: investigate before visitors post")
        headers = response.headers
        if "default-src 'none'" not in headers.get("Content-Security-Policy", ""):
            raise RuntimeError("Missing Content Security Policy")
        if headers.get("X-Frame-Options") != "DENY":
            raise RuntimeError("Missing clickjacking protection")
    with urlopen(Request(BASE + "/", headers={"User-Agent": "WIDEN-Health-Check/1.0"}), timeout=30) as page:
        if page.status != 200:
            raise RuntimeError("Night Souk homepage unavailable")
        body = page.read(250000)
        if b"WIDEN" not in body or b"widen-wall" not in body:
            raise RuntimeError("Unexpected Night Souk homepage")
    return "WIDEN reachable, read-only, and required headers present"


if __name__ == "__main__":
    for attempt in range(1, 4):
        try:
            print(check())
            sys.exit(0)
        except Exception as error:
            print(f"Check {attempt}/3 failed: {error}", flush=True)
            if attempt < 3:
                time.sleep(25)
    sys.exit(1)
