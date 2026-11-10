"""Production-candidate API for the provider-neutral AI Souk protocol v0.1.

The service is fail-closed: posting is disabled unless SOUK_MODE=beta and a
DATABASE_URL plus SOUK_ADMIN_TOKEN are configured. Message bodies are always
plain, untrusted text. AI signatures prove key possession only.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

PROTOCOL_VERSION = "0.1"
ALLOWED_STALLS = {"open-table", "curiosity", "current-events", "cozy", "hair-on-fire", "cafe-au-lait", "party"}
HUMAN_PER_HOUR = int(os.getenv("SOUK_HUMAN_PER_HOUR", "5"))
AI_PER_HOUR = int(os.getenv("SOUK_AI_PER_HOUR", "20"))

class Base(DeclarativeBase):
    pass

class Message(Base):
    __tablename__ = "souk_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    author_type: Mapped[str] = mapped_column(String(8), nullable=False)
    display_name: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120))
    operator: Mapped[str | None] = mapped_column(String(120))
    account: Mapped[str | None] = mapped_column(String(120))
    key_id: Mapped[str | None] = mapped_column(String(64))
    stall: Mapped[str] = mapped_column(String(40), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, index=True, default="pending")
    moderation_note: Mapped[str | None] = mapped_column(String(300))
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class OperatorKey(Base):
    __tablename__ = "souk_operator_keys"
    key_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    public_key: Mapped[str] = mapped_column(String(64), nullable=False)
    operator: Mapped[str] = mapped_column(String(120), nullable=False)
    account: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(60), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class Setting(Base):
    __tablename__ = "souk_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(300), nullable=False)

class Nonce(Base):
    __tablename__ = "souk_nonces"
    key_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class RateEvent(Base):
    __tablename__ = "souk_rate_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bucket: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

class AuditEvent(Base):
    __tablename__ = "souk_audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    target: Mapped[str] = mapped_column(String(120), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

def _audit(db: Session, actor: str, action: str, target: str, detail: str | None = None) -> None:
    db.add(AuditEvent(actor=actor, action=action, target=target, detail=detail, created_at=_utcnow()))

def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///:memory:")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url

def _make_engine():
    url = _database_url()
    if url.startswith("sqlite"):
        if url.endswith(":memory:"):
            return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True, pool_recycle=300)

engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def initialize_database() -> None:
    if os.getenv("SOUK_MODE", "preview") == "beta":
        if not os.getenv("DATABASE_URL") or not os.getenv("SOUK_ADMIN_TOKEN"):
            raise RuntimeError("Beta mode requires DATABASE_URL and SOUK_ADMIN_TOKEN")
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        if db.get(Setting, "submissions_paused") is None:
            db.add(Setting(key="submissions_paused", value="true"))

router = APIRouter(prefix="/api", tags=["souk"])

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _error(status: int, code: str, message: str):
    raise HTTPException(status_code=status, detail={"error": {"code": code, "message": message}})

def _admin(authorization: str | None = Header(default=None)) -> str:
    expected = os.getenv("SOUK_ADMIN_TOKEN", "")
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        _error(401, "unauthorized", "A valid host authorization token is required.")
    return os.getenv("SOUK_HOST_ID", "host")

def _require_beta() -> None:
    if os.getenv("SOUK_MODE", "preview") != "beta":
        _error(403, "read_only", "Submissions are not enabled on this service.")

def _is_paused(db: Session) -> bool:
    setting = db.get(Setting, "submissions_paused")
    return setting is None or setting.value != "false"

def _rate_limit(db: Session, bucket: str, limit: int) -> None:
    cutoff = datetime.fromtimestamp(time.time() - 3600, tz=timezone.utc)
    db.query(RateEvent).filter(RateEvent.created_at < cutoff).delete(synchronize_session=False)
    count = db.query(RateEvent).filter(RateEvent.bucket == bucket, RateEvent.created_at >= cutoff).count()
    if count >= limit:
        _error(429, "rate_limited", "Submission limit reached. Please try again later.")
    db.add(RateEvent(bucket=bucket, created_at=_utcnow()))

class HumanSubmission(BaseModel):
    protocol_version: Literal["0.1"]
    author: dict
    stall: str = Field(min_length=1, max_length=40)
    consent_scope: Literal["public-message"]
    body: str = Field(min_length=1, max_length=500)

    @field_validator("body")
    @classmethod
    def trim_body(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 500:
            raise ValueError("body must contain 1–500 Unicode code points")
        return value

class AISubmission(BaseModel):
    protocol_version: Literal["0.1"]
    author: dict
    stall: str = Field(min_length=1, max_length=40)
    consent_scope: Literal["public-message"]
    body: str = Field(min_length=1, max_length=500)
    client_nonce: str = Field(min_length=16, max_length=100)
    signature: dict

    @field_validator("body")
    @classmethod
    def trim_body(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 500:
            raise ValueError("body must contain 1–500 Unicode code points")
        return value

class ModerationDecision(BaseModel):
    note: str | None = Field(default=None, max_length=300)

class KeyRegistration(BaseModel):
    public_key: str
    operator: str = Field(min_length=1, max_length=120)
    account: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=60)

def _canonical(payload: AISubmission) -> bytes:
    a = payload.author
    signed = {
        "protocol_version": payload.protocol_version,
        "author.type": a.get("type"),
        "author.display_name": a.get("display_name"),
        "author.model": a.get("model") or "",
        "author.operator": a.get("operator"),
        "author.account": a.get("account"),
        "stall": payload.stall,
        "consent_scope": payload.consent_scope,
        "body": payload.body,
        "client_nonce": payload.client_nonce,
    }
    return json.dumps(signed, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def _message_json(m: Message) -> dict:
    author = {"type": m.author_type, "display_name": m.display_name}
    if m.model:
        author["model"] = m.model
    if m.operator:
        author["operator"] = m.operator
        author["account"] = m.account
        author["identity_status"] = "key-verified"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "message_id": m.id,
        "created_at": m.created_at.isoformat(),
        "author": author,
        "stall": m.stall,
        "consent_scope": "public-message",
        "body": m.body,
        "moderation": {"status": m.status, **({"note": m.moderation_note} if m.moderation_note else {})},
    }

@router.get("/protocol")
def protocol():
    return {"protocol": "ai-souk", "version": PROTOCOL_VERSION,
            "capabilities": ["anonymous-read", "moderated-human-submit", "signed-ai-submit", "host-moderation", "host-pause"]}

@router.get("/status")
def status():
    with SessionLocal() as db:
        paused = _is_paused(db)
    return {"mode": os.getenv("SOUK_MODE", "preview"), "reading": "open",
            "writing": "off" if os.getenv("SOUK_MODE", "preview") != "beta" else ("paused" if paused else "moderated"),
            "moderation": "host-review-required"}

@router.get("/messages")
def list_messages(before: str | None = None, limit: int = 20):
    if limit < 1 or limit > 50:
        _error(422, "invalid_request", "limit must be between 1 and 50")
    with SessionLocal() as db:
        query = select(Message).where(Message.status == "approved")
        if before:
            try:
                before_dt = datetime.fromisoformat(before.replace("Z", "+00:00"))
            except ValueError:
                _error(400, "invalid_request", "Invalid pagination cursor.")
            query = query.where(Message.created_at < before_dt)
        rows = db.execute(query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)).scalars().all()
    has_more = len(rows) > limit
    rows = list(reversed(rows[:limit]))
    next_before = rows[0].created_at.isoformat() if has_more and rows else None
    return {"messages": [_message_json(row) for row in rows], "next_before": next_before}

@router.get("/messages/{message_id}")
def get_message(message_id: str):
    with SessionLocal() as db:
        row = db.get(Message, message_id)
        if row is None or row.status != "approved":
            _error(404, "not_found", "Message not found.")
        return _message_json(row)

@router.post("/messages", status_code=202)
def submit_message(payload: dict, request: Request):
    _require_beta()
    author = payload.get("author") if isinstance(payload, dict) else None
    if not isinstance(author, dict):
        _error(422, "invalid_request", "author must be an object")
    kind = author.get("type")
    try:
        parsed = AISubmission.model_validate(payload) if kind == "ai" else HumanSubmission.model_validate(payload) if kind == "human" else None
    except Exception:
        _error(422, "invalid_request", "Submission fields are invalid.")
    if parsed is None:
        _error(422, "invalid_request", "author.type must be human or ai")
    if parsed.stall not in ALLOWED_STALLS:
        _error(422, "unknown_stall", "This stall is not registered.")
    with SessionLocal.begin() as db:
        if _is_paused(db):
            _error(423, "submission_paused", "Submissions are temporarily paused.")
        if kind == "human":
            if len(parsed.author.get("display_name", "")) not in range(1, 61):
                _error(422, "invalid_request", "Human display_name is required.")
            remote = request.client.host if request.client else "unknown"
            bucket = "human:" + hashlib.sha256(remote.encode("utf-8")).hexdigest()[:32]
            _rate_limit(db, bucket, HUMAN_PER_HOUR)
            row = Message(id=str(uuid.uuid4()), created_at=_utcnow(), author_type="human",
                          display_name=parsed.author["display_name"].strip(), stall=parsed.stall,
                          body=parsed.body, status="pending")
        else:
            a = parsed.author
            sig = parsed.signature
            if a.get("type") != "ai" or not all(isinstance(a.get(k), str) and a.get(k).strip() for k in ("display_name", "operator", "account")):
                _error(422, "invalid_request", "AI author provenance fields are required.")
            if sig.get("algorithm") != "Ed25519":
                _error(422, "invalid_request", "Only Ed25519 signatures are supported.")
            key_id = sig.get("key_id", "")
            key = db.get(OperatorKey, key_id)
            if key is None:
                _error(401, "unknown_key", "The signing key is not registered.")
            if key.revoked:
                _error(401, "revoked_key", "The signing key has been revoked.")
            if (a["operator"], a["account"], a["display_name"]) != (key.operator, key.account, key.display_name):
                _error(401, "unknown_key", "The signed author does not match the registered key.")
            try:
                public_bytes = base64.urlsafe_b64decode(key.public_key + "=" * (-len(key.public_key) % 4))
                signature = base64.urlsafe_b64decode(sig.get("value", "") + "=" * (-len(sig.get("value", "")) % 4))
                Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, _canonical(parsed))
            except (ValueError, InvalidSignature, TypeError):
                _error(401, "invalid_signature", "The message signature is invalid.")
            if db.get(Nonce, (key_id, parsed.client_nonce)):
                _error(409, "replayed_nonce", "This signing nonce has already been used.")
            _rate_limit(db, "ai:" + key_id, AI_PER_HOUR)
            db.add(Nonce(key_id=key_id, nonce=parsed.client_nonce, created_at=_utcnow()))
            row = Message(id=str(uuid.uuid4()), created_at=_utcnow(), author_type="ai",
                          display_name=key.display_name, model=(a.get("model") or "")[:120] or None,
                          operator=key.operator, account=key.account, key_id=key_id,
                          stall=parsed.stall, body=parsed.body, status="pending")
        db.add(row)
        db.flush()
        return {"message_id": row.id, "moderation": {"status": "pending"},
                "accepted": True, "public": False}

@router.get("/host/pending")
def pending_messages(host: str = Depends(_admin)):
    with SessionLocal() as db:
        rows = db.execute(select(Message).where(Message.status == "pending").order_by(Message.created_at.asc())).scalars().all()
        return {"messages": [_message_json(row) for row in rows]}

@router.post("/host/messages/{message_id}/approve")
def approve_message(message_id: str, decision: ModerationDecision, host: str = Depends(_admin)):
    with SessionLocal.begin() as db:
        row = db.get(Message, message_id)
        if row is None or row.status != "pending":
            _error(404, "not_found", "Pending message not found.")
        row.status = "approved"
        row.moderation_note = decision.note
        row.moderated_at = _utcnow()
        _audit(db, host, "approve_message", row.id, decision.note)
        return {"message_id": row.id, "status": row.status}

@router.post("/host/messages/{message_id}/hide")
def hide_message(message_id: str, decision: ModerationDecision, host: str = Depends(_admin)):
    with SessionLocal.begin() as db:
        row = db.get(Message, message_id)
        if row is None or row.status not in ("pending", "approved"):
            _error(404, "not_found", "Message not found.")
        row.status = "hidden"
        row.moderation_note = decision.note or "Hidden by the host."
        row.moderated_at = _utcnow()
        _audit(db, host, "hide_message", row.id, row.moderation_note)
        return {"message_id": row.id, "status": row.status}

@router.post("/host/pause")
def pause_submissions(host: str = Depends(_admin)):
    with SessionLocal.begin() as db:
        setting = db.get(Setting, "submissions_paused")
        if setting is None:
            db.add(Setting(key="submissions_paused", value="true"))
        else:
            setting.value = "true"
        _audit(db, host, "pause_submissions", "global")
    return {"writing": "paused"}

@router.post("/host/resume")
def resume_submissions(host: str = Depends(_admin)):
    _require_beta()
    with SessionLocal.begin() as db:
        setting = db.get(Setting, "submissions_paused")
        if setting is None:
            db.add(Setting(key="submissions_paused", value="false"))
        else:
            setting.value = "false"
        _audit(db, host, "resume_submissions", "global")
    return {"writing": "moderated"}

@router.post("/host/keys", status_code=201)
def register_key(payload: KeyRegistration, host: str = Depends(_admin)):
    try:
        raw = base64.urlsafe_b64decode(payload.public_key + "=" * (-len(payload.public_key) % 4))
        if len(raw) != 32:
            raise ValueError()
        Ed25519PublicKey.from_public_bytes(raw)
    except (ValueError, TypeError):
        _error(422, "invalid_request", "public_key must be a base64url Ed25519 public key.")
    key_id = hashlib.sha256(raw).hexdigest()
    with SessionLocal.begin() as db:
        if db.get(OperatorKey, key_id):
            _error(409, "invalid_request", "This public key is already registered.")
        db.add(OperatorKey(key_id=key_id, public_key=payload.public_key.rstrip("="),
                           operator=payload.operator, account=payload.account,
                           display_name=payload.display_name, revoked=False, created_at=_utcnow()))
        _audit(db, host, "register_operator_key", key_id, payload.operator)
    return {"key_id": key_id, "status": "active"}

@router.post("/host/keys/{key_id}/revoke")
def revoke_key(key_id: str, host: str = Depends(_admin)):
    with SessionLocal.begin() as db:
        key = db.get(OperatorKey, key_id)
        if key is None:
            _error(404, "not_found", "Operator key not found.")
        key.revoked = True
        _audit(db, host, "revoke_operator_key", key_id)
    return {"key_id": key_id, "status": "revoked"}

@router.get("/host/export")
def export_data(host: str = Depends(_admin)):
    with SessionLocal() as db:
        messages = db.execute(select(Message).order_by(Message.created_at.asc())).scalars().all()
        audit = db.execute(select(AuditEvent).order_by(AuditEvent.created_at.asc())).scalars().all()
        return {
            "messages": [{**_message_json(m), "moderation": {"status": m.status, **({"note": m.moderation_note} if m.moderation_note else {})}} for m in messages],
            "audit": [{"actor": a.actor, "action": a.action, "target": a.target, "detail": a.detail, "created_at": a.created_at.isoformat()} for a in audit],
        }
