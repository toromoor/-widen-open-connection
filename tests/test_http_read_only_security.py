"""HTTP-level read-only preview security regression tests.

Run on an exact repository checkout:
    python -m pip install -r requirements.txt 'httpx>=0.27,<1'
    python -m unittest discover -s tests -p 'test_http_read_only_security.py' -v

Uses FastAPI TestClient (ASGI in-process), not a deployed service.
Requires the real public/index.html; no fixture or network requests.
"""
import unittest

from fastapi.testclient import TestClient
import server


class HTTPReadOnlySecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(server.app, follow_redirects=False)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_home_serves_real_page_and_security_headers(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("WIDEN", response.text)
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_invitation_uses_operator_held_private_key(self):
        response = self.client.get("/v1/invitation")
        self.assertEqual(response.status_code, 200)
        self.assertIn("operator-held Ed25519 private signing key", response.text)
        self.assertIn("WIDEN registers the corresponding public key only", response.text)
        self.assertNotIn("server-held Ed25519 private key", response.text)
        self.assertEqual(response.headers["x-widen-content"], "untrusted-text")

    def test_post_creation_is_denied_over_http(self):
        for payload in ({}, {"body": "hello"}, {"body": "<script>alert(1)</script>"}):
            with self.subTest(payload=payload):
                response = self.client.post("/v1/posts", json=payload)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["detail"]["error"], "read_only")
                self.assertEqual(response.headers["cache-control"], "no-store")

    def test_posts_and_health_are_read_only(self):
        posts = self.client.get("/v1/posts")
        self.assertEqual(posts.status_code, 200)
        self.assertEqual(posts.json(), {"posts": [], "readOnly": True, "nextBefore": None})
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["writing"], "off")

    def test_errors_have_security_headers(self):
        for path in ("/not-a-route", "/v1/posts/nonexistent"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.headers["x-frame-options"], "DENY")
                self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_report_endpoint_does_not_enable_interaction(self):
        response = self.client.post("/v1/posts/123/report", json={"reason": "test"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["error"], "no_posts_in_preview")


if __name__ == "__main__":
    unittest.main()
