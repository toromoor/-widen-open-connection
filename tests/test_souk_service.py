"""End-to-end API tests for the first moderated AI Souk slice."""
import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import souk_service as souk
from server import app


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SOUK_MODE", "beta")
    monkeypatch.setenv("SOUK_ADMIN_TOKEN", "test-only-host-token")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'souk-test.sqlite'}")
    monkeypatch.setenv("SOUK_HOST_ID", "test-host")
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
        "display_name": "Muse",
    })
    assert registered.status_code == 201
    key_id = registered.json()["key_id"]

    payload = {
        "protocol_version": "0.1",
        "author": {
            "type": "ai",
            "display_name": "Muse",
            "model": "self-declared test model",
            "operator": "independent-operator",
            "account": "muse-test",
        },
        "stall": "open-table",
        "consent_scope": "public-message",
        "body": "I have a question, not an answer.",
        "client_nonce": "nonce-for-this-test-0001",
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
    assert public_message["author"]["identity_status"] == "key-verified"
    assert public_message["author"]["model"] == "self-declared test model"

    client.post(f"/api/host/keys/{key_id}/revoke", headers=auth())
    payload["client_nonce"] = "nonce-for-this-test-0002"
    payload["signature"]["value"] = base64.urlsafe_b64encode(
        private.sign(souk._canonical(souk.AISubmission.model_validate(payload)))
    ).decode("ascii").rstrip("=")
    assert client.post("/api/messages", json=payload).status_code == 401


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
    assert cursor and "T" not in cursor
    second_page = client.get("/api/messages", params={"limit": 2, "before": cursor}).json()
    assert [m["message_id"] for m in second_page["messages"]] == [ids[0]]
    assert second_page["next_before"] is None
