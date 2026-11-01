"""Fail-closed tests for WIDEN preview. These run in GitHub Actions."""
import base64
import hashlib
import re

from fastapi.testclient import TestClient
from server import ROOT, app

client = TestClient(app)


def test_read_only_by_default():
    result = client.get("/health")
    assert result.status_code == 200
    assert result.json() == {"ok": True, "writing": "off", "mode": "read-only-preview"}
    assert client.get("/v1/posts").json() == {"posts": [], "readOnly": True, "nextBefore": None}


def test_writes_and_unknown_posts_do_not_open_access():
    result = client.post("/v1/posts", json={"text": "untrusted", "kind": "idea"})
    assert result.status_code == 403
    assert result.json()["detail"]["error"] == "read_only"
    assert client.get("/v1/posts/not-an-existing-post").status_code == 404
    assert client.post("/v1/posts/nope/report", json={}).status_code == 404
    assert client.get("/docs").status_code == 404


def test_browser_security_headers():
    for url in ("/", "/health", "/v1/invitation", "/v1/rules", "/does-not-exist"):
        r = client.get(url)
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert r.headers["cache-control"] == "no-store"
        assert "camera=()" in r.headers["permissions-policy"]
        assert "default-src 'none'" in r.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        assert "object-src 'none'" in r.headers["content-security-policy"]
        assert "connect-src 'self'" in r.headers["content-security-policy"]
        script_policy = r.headers["content-security-policy"].split("script-src ", 1)[1].split(";", 1)[0]
        assert "'unsafe-inline'" not in script_policy


def test_exact_inline_js_is_allowed_by_hash_not_all_inline_scripts():
    html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", html, flags=re.I | re.S)
    assert scripts
    csp = client.get("/").headers["content-security-policy"]
    for s in scripts:
        digest = base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode("ascii")
        assert f"'sha256-{digest}'" in csp


def test_page_contains_honest_empty_wall():
    page = client.get("/")
    assert page.status_code == 200
    assert "widen-wall" in page.text
    assert "writing is closed" in page.text
    assert "Night Souk" in page.text or "night SOUK" in page.text
