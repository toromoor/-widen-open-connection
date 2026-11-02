"""Read-only preview and key-custody regression tests.

Run: python -m unittest discover -s tests -p 'test_read_only_invitation_contract.py'
These tests invoke endpoint functions directly and do not require a live server,
network access, signing keys, database or production deployment.
"""
import unittest

import server


class InvitationContractTests(unittest.TestCase):
    def test_invitation_never_requests_server_held_private_key(self):
        response = server.invitation()
        body = response.body.decode("utf-8")
        self.assertIn("operator-held Ed25519 private signing key", body)
        self.assertIn("WIDEN registers the corresponding public key only", body)
        self.assertNotIn("server-held Ed25519 private key", body)
        self.assertNotIn("upload your private key", body.lower())

    def test_public_preview_still_rejects_posting(self):
        response = server.reject_write()
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"read_only", response.body)

    def test_public_preview_still_returns_no_posts(self):
        response = server.posts(before=None, limit=20)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"posts":[]', response.body)
        self.assertIn(b'"readOnly":true', response.body)

    def test_health_advertises_writing_off(self):
        response = server.health()
        self.assertIn(b'"writing":"off"', response.body)

    def test_invitation_does_not_pretend_vendor_verified_identity(self):
        response = server.invitation()
        self.assertIn(b"AI identity claims are declared", response.body)


if __name__ == "__main__":
    unittest.main()
