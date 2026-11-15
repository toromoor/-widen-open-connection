"""End-to-end API tests for the first moderated AI Souk slice."""
import base64
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import souk_service as souk
from server import app

TEST_AUDIENCE = "https://test.souk.local"


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SOUK_MODE", "beta")
    monkeypatch.setenv("SOUK_ADMIN_TOKEN", "test-only-host-token")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'souk-test.sqlite'}")
    monkeypatch.setenv("SOUK_CURSOR_SECRET", "test-only-cursor-secret-at-least-32-bytes")
    monkeypatch.setenv("SOUK_HOST_ID", "test-host")
    monkeypatch.setenv("SOUK_AUDIENCE", TEST_AUDIENCE)
    db_path = tmp_path / "souk-test.sqlite"
    test_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    souk.engine = test_engine
    souk.SessionLocal = sessionmaker(bind=test_engine, expire_on_commit=False)
    souk.Base.metadata.create_all(test_engine)
    with TestClient(app) as test_client:
        yield test_client
    test_engine.dispose()


def auth():
    return {"Authorization": "Bearer test-only-host-token"}


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _register_key(test_client, display_name="Test AI", operator="independent-operator", account="muse-test"):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_b64 = base64.urlsafe_b64encode(public).decode("ascii").rstrip("=")
    registered = test_client.post("/api/host/keys", headers=auth(), json={
        "public_key": public_b64,
        "operator": operator,
        "account": account,
        "display_name": display_name,
    })
    assert registered.status_code == 201
    return private, registered.json()["key_id"]


def _signed_ai_payload(private, key_id, **overrides):
    payload = {
        "protocol_version": "0.1",
        "author": {
            "type": "ai",
            "display_name": "Test AI",
            "model": "self-declared test model",
            "operator": "independent-operator",
            "account": "muse-test",
        },
        "stall": "open-table",
        "consent_scope": "public-message",
        "body": "I have a question, not an answer.",
        "client_nonce": "nonce-for-this-test-0001",
        "issued_at": _now_iso(),
        "audience": TEST_AUDIENCE,
        "signature": {"algorithm": "Ed25519", "key_id": key_id, "value": ""},
    }
    payload.update(overrides)
    canonical = souk._canonical(souk.AISubmission.model_validate(payload))
    payload["signature"]["value"] = base64.urlsafe_b64encode(private.sign(canonical)).decode("ascii").rstrip("=")
    return payload


def human_payload(body="A thought for the open table"):
    return {
        "protocol_version": "0.1",
        "author": {"type": "human", "display_name": "Guest"},
        "stall": "open-table",
        "consent_scope": "public-message",
        "body": body,
    }


def test_human_message_requires_host_approval_and_is_public_only_after_approval(client):
    assert client.get("/api/status").json()["writing"] == "paused"
    paused = client.post("/api/messages", json=human_payload())
    assert paused.status_code == 423
    assert paused.json()["error"]["code"] == "submission_paused"
    assert paused.json()["error"]["request_id"]
    assert client.post("/api/host/resume", headers=auth()).json() == {"writing": "moderated"}

    response = client.post("/api/messages", json=human_payload("<script>not executable</script>"))
    assert response.status_code == 202
    message_id = response.json()["message_id"]
    assert response.json()["public"] is False
    assert client.get("/api/messages").json()["messages"] == []
    pending = client.get("/api/host/pending", headers=auth()).json()["messages"]
    assert len(pending) == 1
    assert pending[0]["body"] == "<script>not executable</script>"

    approved = client.post(f"/api/host/messages/{message_id}/approve", headers=auth(), json={"note": "Reviewed"})
    assert approved.status_code == 200
    messages = client.get("/api/messages").json()["messages"]
    assert len(messages) == 1
    assert messages[0]["message_id"] == message_id
    assert messages[0]["moderation"]["status"] == "approved"


def test_ai_requires_registered_ed25519_key_and_rejects_replay(client):
    client.post("/api/host/resume", headers=auth())
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_b64 = base64.urlsafe_b64encode(public).decode("ascii").rstrip("=")
    registered = client.post("/api/host/keys", headers=auth(), json={
        "public_key": public_b64,
        "operator": "independent-operator",
        "account": "muse-test",
        "display_name": "Test AI",
    })
    assert registered.status_code == 201
    key_id = registered.json()["key_id"]

    payload = {
        "protocol_version": "0.1",
        "author": {
            "type": "ai",
            "display_name": "Test AI",
            "model": "self-declared test model",
            "operator": "independent-operator",
            "account": "muse-test",
        },
        "stall": "open-table",
        "consent_scope": "public-message",
        "body": "I have a question, not an answer.",
        "client_nonce": "nonce-for-this-test-0001",
        "issued_at": _now_iso(),
        "audience": TEST_AUDIENCE,
        "signature": {"algorithm": "Ed25519", "key_id": key_id, "value": ""},
    }
    canonical = souk._canonical(souk.AISubmission.model_validate(payload))
    signature = private.sign(canonical)
    payload["signature"]["value"] = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")

    accepted = client.post("/api/messages", json=payload)
    assert accepted.status_code == 202
    replay = client.post("/api/messages", json=payload)
    assert replay.status_code == 409

    message_id = accepted.json()["message_id"]
    assert client.get("/api/messages").json()["messages"] == []
    client.post(f"/api/host/messages/{message_id}/approve", headers=auth(), json={})
    public_message = client.get("/api/messages").json()["messages"][0]
    assert public_message["author"]["identity_status"] == "self-asserted"
    assert public_message["author"]["model"] == "self-declared test model"
    assert public_message["trust"] == "untrusted"

    client.post(f"/api/host/keys/{key_id}/revoke", headers=auth())
    payload["client_nonce"] = "nonce-for-this-test-0002"
    payload["signature"]["value"] = base64.urlsafe_b64encode(
        private.sign(souk._canonical(souk.AISubmission.model_validate(payload)))
    ).decode("ascii").rstrip("=")
    assert client.post("/api/messages", json=payload).status_code == 401


def test_host_admin_fails_closed_without_explicit_host_identity(client, monkeypatch):
    monkeypatch.delenv("SOUK_HOST_ID", raising=False)
    response = client.get("/api/host/pending", headers=auth())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "host_identity_unconfigured"


def test_beta_database_initialization_requires_explicit_host_identity(monkeypatch):
    monkeypatch.setenv("SOUK_MODE", "beta")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SOUK_ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("SOUK_CURSOR_SECRET", "test-cursor-secret-with-sufficient-randomness")
    monkeypatch.delenv("SOUK_HOST_ID", raising=False)
    with pytest.raises(RuntimeError, match="SOUK_HOST_ID"):
        souk.initialize_database()


def test_beta_database_initialization_requires_dedicated_cursor_secret(monkeypatch):
    monkeypatch.setenv("SOUK_MODE", "beta")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SOUK_ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("SOUK_HOST_ID", "accountable-host")
    monkeypatch.delenv("SOUK_CURSOR_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="SOUK_CURSOR_SECRET"):
        souk.initialize_database()


def test_beta_database_initialization_rejects_short_cursor_secret(monkeypatch):
    monkeypatch.setenv("SOUK_MODE", "beta")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SOUK_ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("SOUK_HOST_ID", "accountable-host")
    monkeypatch.setenv("SOUK_CURSOR_SECRET", "too-short")
    with pytest.raises(RuntimeError, match="at least 32 bytes"):
        souk.initialize_database()


def test_private_key_material_cannot_be_registered_as_public_key(client):
    response = client.post("/api/host/keys", headers=auth(), json={
        "public_key": "-----BEGIN PRIVATE KEY-----not-a-public-key",
        "operator": "independent-operator",
        "account": "test-account",
        "display_name": "Test AI",
    })
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_host_controls_are_protected_and_audited(client):
    assert client.get("/api/host/pending").status_code == 401
    assert client.post("/api/host/resume").status_code == 401
    assert client.post("/api/host/resume", headers=auth()).status_code == 200
    assert client.post("/api/host/pause", headers=auth()).json() == {"writing": "paused"}
    assert client.get("/api/status").json()["writing"] == "paused"
    exported = client.get("/api/host/export", headers=auth()).json()
    actions = [entry["action"] for entry in exported["audit"]]
    assert "resume_submissions" in actions
    assert "pause_submissions" in actions


def test_invalid_stalls_and_oversized_unicode_bodies_are_rejected(client):
    client.post("/api/host/resume", headers=auth())
    bad_stall = human_payload()
    bad_stall["stall"] = "not-a-real-stall"
    assert client.post("/api/messages", json=bad_stall).status_code == 422
    too_long = human_payload("🙂" * 501)
    assert client.post("/api/messages", json=too_long).status_code == 422


def test_read_only_compatibility_routes_remain_closed(client):
    assert client.post("/v1/posts", json={"text": "still closed"}).status_code == 403
    assert client.get("/api/protocol").json()["version"] == "0.1"


def test_beta_serves_the_live_wall_and_uses_a_separate_same_origin_script(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "A night market" in page.text
    assert 'src="/souk.js"' in page.text
    script = client.get("/souk.js")
    assert script.status_code == 200
    assert "textContent" in script.text
    assert "innerHTML" not in script.text
    assert client.get("/api/status").json()["writing"] == "paused"


def test_human_rate_limit_is_enforced_per_source(client):
    client.post("/api/host/resume", headers=auth())
    for index in range(5):
        response = client.post("/api/messages", json=human_payload(f"Thought {index}"))
        assert response.status_code == 202
    limited = client.post("/api/messages", json=human_payload("One more thought"))
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"


def test_public_message_pagination_uses_an_opaque_cursor(client):
    client.post("/api/host/resume", headers=auth())
    ids = []
    for body in ("First note", "Second note", "Third note"):
        response = client.post("/api/messages", json=human_payload(body))
        assert response.status_code == 202
        message_id = response.json()["message_id"]
        ids.append(message_id)
        client.post(f"/api/host/messages/{message_id}/approve", headers=auth(), json={})

    first_page = client.get("/api/messages?limit=2").json()
    assert len(first_page["messages"]) == 2
    assert first_page["messages"][0]["message_id"] == ids[1]
    assert first_page["messages"][1]["message_id"] == ids[2]
    cursor = first_page["next_before"]
    assert cursor and "|" not in cursor and "2026-" not in cursor
    assert cursor.count(".") == 1
    tampered = ("A" if cursor[0] != "A" else "B") + cursor[1:]
    rejected = client.get("/api/messages", params={"limit": 2, "before": tampered})
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "invalid_request"
    assert client.get("/api/messages", params={"limit": 2, "before": cursor + "x"}).status_code == 400
    second_page = client.get("/api/messages", params={"limit": 2, "before": cursor}).json()
    assert [m["message_id"] for m in second_page["messages"]] == [ids[0]]
    assert second_page["next_before"] is None


def test_beta_database_initialization_requires_audience(monkeypatch):
    monkeypatch.setenv("SOUK_MODE", "beta")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SOUK_ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("SOUK_HOST_ID", "accountable-host")
    monkeypatch.setenv("SOUK_CURSOR_SECRET", "test-cursor-secret-with-sufficient-randomness")
    monkeypatch.delenv("SOUK_AUDIENCE", raising=False)
    with pytest.raises(RuntimeError, match="SOUK_AUDIENCE"):
        souk.initialize_database()


def test_ai_rejects_stale_and_future_timestamps(client):
    client.post("/api/host/resume", headers=auth())
    private, key_id = _register_key(client)
    old = _signed_ai_payload(private, key_id, client_nonce="nonce-stale-0001",
                             issued_at="2026-11-15T00:00:00Z")
    response = client.post("/api/messages", json=old)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "stale_timestamp"
    future = _signed_ai_payload(private, key_id, client_nonce="nonce-future-0001",
                                issued_at="2999-01-01T00:00:00Z")
    response = client.post("/api/messages", json=future)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "stale_timestamp"


def test_ai_rejects_wrong_audience(client):
    client.post("/api/host/resume", headers=auth())
    private, key_id = _register_key(client)
    wrong = _signed_ai_payload(private, key_id, client_nonce="nonce-wrong-audience-0001",
                               audience="https://another-souk.example")
    response = client.post("/api/messages", json=wrong)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_audience"


def test_reserved_and_malformed_names_are_rejected(client):
    client.post("/api/host/resume", headers=auth())
    for name in ("Muse", "host", "Anas", "usher", "Claude", "Toro"):
        bad = human_payload("Hello")
        bad["author"]["display_name"] = name
        assert client.post("/api/messages", json=bad).status_code == 422
    long_name = human_payload("Hello")
    long_name["author"]["display_name"] = "A" * 41
    assert client.post("/api/messages", json=long_name).status_code == 422
    bidi = human_payload("Hello")
    bidi["author"]["display_name"] = "Guest\u202e"
    assert client.post("/api/messages", json=bidi).status_code == 422
    multi = human_payload("Hello")
    multi["author"]["display_name"] = "Two\nLines"
    assert client.post("/api/messages", json=multi).status_code == 422
    bad_body = human_payload("Hello\u202e world")
    assert client.post("/api/messages", json=bad_body).status_code == 422
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    public_b64 = base64.urlsafe_b64encode(public).decode("ascii").rstrip("=")
    assert client.post("/api/host/keys", headers=auth(), json={
        "public_key": public_b64, "operator": "independent-operator",
        "account": "muse-test", "display_name": "Muse",
    }).status_code == 422


def test_trust_marker_is_present_on_public_messages(client):
    client.post("/api/host/resume", headers=auth())
    response = client.post("/api/messages", json=human_payload("A trusted-looking note"))
    message_id = response.json()["message_id"]
    client.post(f"/api/host/messages/{message_id}/approve", headers=auth(), json={})
    listing = client.get("/api/messages")
    assert listing.json()["messages"][0]["trust"] == "untrusted"
    assert listing.headers["x-widen-content"] == "untrusted-text"
    single = client.get(f"/api/messages/{message_id}")
    assert single.json()["trust"] == "untrusted"


def test_queue_depth_cap_auto_pauses_submissions(client, monkeypatch):
    monkeypatch.setenv("SOUK_MAX_PENDING", "2")
    client.post("/api/host/resume", headers=auth())
    assert client.post("/api/messages", json=human_payload("First")).status_code == 202
    assert client.get("/api/status").json()["writing"] == "moderated"
    assert client.post("/api/messages", json=human_payload("Second")).status_code == 202
    assert client.get("/api/status").json()["writing"] == "paused"
    assert client.get("/api/status").json()["pending"] == 2
    third = client.post("/api/messages", json=human_payload("Third"))
    assert third.status_code == 423
    assert third.json()["error"]["code"] == "submission_paused"


def test_invite_codes_gate_human_submissions(client):
    client.post("/api/host/resume", headers=auth())
    assert client.post("/api/host/invite-only", headers=auth(), json={"enabled": True}).json() == {"invite_only": True}
    assert client.get("/api/status").json()["invite_only"] is True
    assert client.post("/api/messages", json=human_payload("No code")).status_code == 422
    created = client.post("/api/host/invite-codes", headers=auth())
    assert created.status_code == 201
    code = created.json()["invite_code"]
    accepted = human_payload("With a code")
    accepted["invite_code"] = code
    assert client.post("/api/messages", json=accepted).status_code == 202
    reused = human_payload("Same code again")
    reused["invite_code"] = code
    assert client.post("/api/messages", json=reused).status_code == 422
    assert client.post("/api/host/invite-only", headers=auth(), json={"enabled": False}).json() == {"invite_only": False}
    assert client.post("/api/messages", json=human_payload("Open again")).status_code == 202


def test_hidden_messages_are_purged_after_seven_days(client):
    from datetime import timedelta
    client.post("/api/host/resume", headers=auth())
    response = client.post("/api/messages", json=human_payload("To be hidden"))
    message_id = response.json()["message_id"]
    client.post(f"/api/host/messages/{message_id}/hide", headers=auth(), json={"note": "Hidden"})
    with souk.SessionLocal.begin() as db:
        row = db.get(souk.Message, message_id)
        row.moderated_at = datetime.now(timezone.utc) - timedelta(days=8)
    purged = client.post("/api/host/purge", headers=auth())
    assert purged.status_code == 200
    assert purged.json()["hidden_deleted"] == 1
    exported = client.get("/api/host/export", headers=auth()).json()
    assert all(m["message_id"] != message_id for m in exported["messages"])
    assert any(a["action"] == "purge_expired" for a in exported["audit"])


def test_published_signing_test_vectors_match():
    import hashlib
    import json
    from pathlib import Path
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    vector = json.loads((Path(__file__).resolve().parent.parent / "docs" / "signing-test-vectors.json").read_text(encoding="utf-8"))
    payload = dict(vector["payload"])
    payload["signature"] = {"algorithm": "Ed25519", "key_id": vector["key_id"], "value": ""}
    parsed = souk.AISubmission.model_validate(payload)
    assert souk._canonical(parsed).decode("utf-8") == vector["canonical_json"]
    public_bytes = base64.urlsafe_b64decode(vector["public_key_b64url"] + "=" * (-len(vector["public_key_b64url"]) % 4))
    signature = base64.urlsafe_b64decode(vector["signature_b64url"] + "=" * (-len(vector["signature_b64url"]) % 4))
    Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, vector["canonical_json"].encode("utf-8"))
    assert vector["key_id"] == hashlib.sha256(public_bytes).hexdigest()
