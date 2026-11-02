"""Fail-closed HTTP method matrix for the public read-only preview.

Run from an exact repository checkout:
    python -m pip install -r requirements.txt 'httpx>=0.27,<1'
    python -m unittest discover -s tests -p 'test_http_read_only_method_matrix.py' -v

These are in-process ASGI tests, not proof of live Render behavior.
"""
import unittest

from fastapi.testclient import TestClient
import server


class HTTPMethodMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(server.app, follow_redirects=False)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_mutating_methods_cannot_change_any_public_resource(self):
        # No method override or alternate HTTP verb should create data.
        paths = ("/", "/health", "/v1/invitation", "/v1/rules",
                 "/v1/posts", "/v1/posts/abc", "/v1/posts/abc/report")
        for path in paths:
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                with self.subTest(path=path, method=method):
                    response = self.client.request(
                        method, path,
                        headers={"X-HTTP-Method-Override": "GET"},
                        json={"body": "attempted mutation"},
                    )
                    self.assertIn(response.status_code, (403, 404, 405))
                    self.assertEqual(response.headers.get("cache-control"), "no-store")
                    self.assertEqual(response.headers.get("x-content-type-options"), "nosniff")

    def test_csp_does_not_permit_arbitrary_inline_script_or_eval(self):
        for path in ("/", "/v1/invitation", "/not-a-route"):
            with self.subTest(path=path):
                response = self.client.get(path)
                csp = response.headers["content-security-policy"]
                self.assertIn("default-src 'none'", csp)
                self.assertIn("frame-ancestors 'none'", csp)
                self.assertIn("object-src 'none'", csp)
                self.assertIn("base-uri 'none'", csp)
                self.assertNotIn("'unsafe-eval'", csp)
                script_directive = next(
                    part.strip() for part in csp.split(";")
                    if part.strip().startswith("script-src ")
                )
                self.assertNotIn("'unsafe-inline'", script_directive)

    def test_method_override_headers_do_not_enable_posting(self):
        for header in ("X-HTTP-Method-Override", "X-Method-Override"):
            with self.subTest(header=header):
                response = self.client.post(
                    "/v1/posts", headers={header: "GET"}, json={"body": "hello"}
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["detail"]["error"], "read_only")

    def test_public_read_state_remains_empty_after_denied_writes(self):
        before = self.client.get("/v1/posts").json()
        self.client.post("/v1/posts", json={"body": "should not persist"})
        after = self.client.get("/v1/posts").json()
        self.assertEqual(before, after)
        self.assertEqual(after["posts"], [])
        self.assertIs(after["readOnly"], True)


if __name__ == "__main__":
    unittest.main()
