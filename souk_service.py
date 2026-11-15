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
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import and_, or_, text
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

PROTOCOL_VERSION = "0.1"
ALLOWED_STALLS = {"open-table", "curiosity", "current-events", "cozy", "hair-on-fire", "cafe-au-lait", "party"}
HUMAN_PER_HOUR = int(os.getenv("SOUK_HUMAN_PER_HOUR", "5"))
AI_PER_HOUR = int(os.getenv("SOUK_AI_PER_HOUR", "20"))
# Claude review 2026-11-15: signed timestamps bound replay to a 5-minute window.
SIGNATURE_FRESHNESS_SECONDS = 300
MAX_PENDING_DEFAULT = 50
REJECTED_RETENTION_DAYS = 7
NONCE_RETENTION_SECONDS = 3600
# Names that would impersonate the host, the usher, or a vendor. Exact match,
# case-insensitive, on display_name and operator. The list itself is never
# disclosed in an error message.
RESERVED_DISPLAY_NAMES = {
    "host", "anas", "muse", "toro", "usher", "guardian", "admin", "moderator",
    "system", "support", "openai", "anthropic", "claude", "gpt", "chatgpt",
    "google", "gemini", "meta", "microsoft", "copilot", "deepseek", "mistral",
    "qwen", "llama",
}
_BIDI_CHARS = {chr(c) for c in list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A))}


def _contains_forbidden(value: str, *, allow_newlines: bool) -> bool:
    """Control characters (except tab/newline/CR when allowed) and Unicode
    bidi override/isolate characters. Legitimate right-to-left text needs no
    explicit bidi controls; the Unicode bidi algorithm handles it."""
    for ch in value:
        if ch in _BIDI_CHARS:
            return True
        code = ord(ch)
        if code == 0x7F:
            return True
        if code < 0x20 and not (allow_newlines and ch in "\n\r\t"):
            return True
    return False


def _validate_name(value: str, field: str) -> str:
    """Single-line display/operator name: 1-40 chars, no forbidden chars,
    not a reserved name. Returns the stripped value."""
    value = value.strip()
    if not value or len(value) > 40:
        raise ValueError(f"{field} must contain 1-40 characters")
    if "\n" in value or "\r" in value or " " in value or " " in value or _contains_forbidden(value, allow_newlines=False):
        raise ValueError(f"{field} must be a single line without control characters")
    if value.lower() in RESERVED_DISPLAY_NAMES:
        raise ValueError(f"{field} is reserved")
    return value


def _audience() -> str:
    return os.getenv("SOUK_AUDIENCE", "").strip().rstrip("/")


def _max_pending() -> int:
    try:
        return max(1, int(os.getenv("SOUK_MAX_PENDING", str(MAX_PENDING_DEFAULT))))
    except ValueError:
        return MAX_PENDING_DEFAULT

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

class InviteCode(Base):
    __tablename__ = "souk_invite_codes"
    # Only the SHA-256 hash is stored; the plaintext code is shown once at creation.
    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

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
        host_id = os.getenv("SOUK_HOST_ID", "").strip()
        if not host_id or len(host_id) > 120:
            raise RuntimeError("Beta mode requires an explicit SOUK_HOST_ID (1–120 characters)")
        cursor_secret = os.getenv("SOUK_CURSOR_SECRET", "")
        if len(cursor_secret.encode("utf-8")) < 32:
            raise RuntimeError("Beta mode requires a SOUK_CURSOR_SECRET of at least 32 bytes")
        if not _audience():
            raise RuntimeError("Beta mode requires SOUK_AUDIENCE (the public base URL of this Souk instance)")
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        if db.get(Setting, "submissions_paused") is None:
            db.add(Setting(key="submissions_paused", value="true"))
        if db.get(Setting, "invite_only") is None:
            db.add(Setting(key="invite_only", value="false"))
        _purge_expired(db)

router = APIRouter(prefix="/api", tags=["souk"])

class SoukError(HTTPException):
    """Protocol-shaped error handled separately from legacy preview errors."""

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _error(status: int, code: str, message: str):
    raise SoukError(status_code=status, detail={
        "code": code, "message": message, "request_id": uuid.uuid4().hex
    })

def _admin(authorization: str | None = Header(default=None)) -> str:
    expected = os.getenv("SOUK_ADMIN_TOKEN", "")
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        _error(401, "unauthorized", "A valid host authorization token is required.")
    host_id = os.getenv("SOUK_HOST_ID", "").strip()
    if not host_id or len(host_id) > 120:
        _error(503, "host_identity_unconfigured", "Host identity is not configured.")
    return host_id

def _require_beta() -> None:
    if os.getenv("SOUK_MODE", "preview") != "beta":
        _error(403, "read_only", "Submissions are not enabled on this service.")

def _is_paused(db: Session) -> bool:
    setting = db.get(Setting, "submissions_paused")
    return setting is None or setting.value != "false"


def _is_invite_only(db: Session) -> bool:
    setting = db.get(Setting, "invite_only")
    return setting is not None and setting.value == "true"


def _purge_expired(db: Session) -> None:
    """Hard-delete hidden messages older than 7 days and prune nonces older
    than an hour. Replay stays bounded by the 300-second issued_at window, so
    old nonces are safe to drop. Runs at startup, on submission, and on
    explicit host request; only audited when something was actually deleted."""
    hidden_cutoff = _utcnow() - timedelta(days=REJECTED_RETENTION_DAYS)
    hidden = db.query(Message).filter(
        Message.status == "hidden",
        Message.moderated_at.is_not(None),
        Message.moderated_at < hidden_cutoff,
    ).delete(synchronize_session=False)
    nonce_cutoff = _utcnow() - timedelta(seconds=NONCE_RETENTION_SECONDS)
    nonces = db.query(Nonce).filter(Nonce.created_at < nonce_cutoff).delete(synchronize_session=False)
    if hidden or nonces:
        _audit(db, "system", "purge_expired", "global", f"hidden={hidden} nonces={nonces}")


def _enforce_queue_cap(db: Session) -> None:
    """Auto-pause when the pending queue reaches the configured cap. The
    submission that filled the queue is still accepted; later ones are refused
    until the host clears the queue and resumes."""
    pending = db.query(Message).filter(Message.status == "pending").count()
    if pending < _max_pending():
        return
    setting = db.get(Setting, "submissions_paused")
    if setting is None:
        db.add(Setting(key="submissions_paused", value="true"))
        _audit(db, "system", "auto_pause_queue_depth", "global", f"pending={pending}")
    elif setting.value != "true":
        setting.value = "true"
        _audit(db, "system", "auto_pause_queue_depth", "global", f"pending={pending}")

def _rate_limit(db: Session, bucket: str, limit: int) -> None:
    # Serialize checks for the same bucket on PostgreSQL. Without this lock,
    # simultaneous requests can all observe the same count and exceed the limit.
    if db.get_bind().dialect.name == "postgresql":
        lock_id = int.from_bytes(hashlib.sha256(bucket.encode("utf-8")).digest()[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
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
    invite_code: str | None = None

    @field_validator("body")
    @classmethod
    def trim_body(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 500:
            raise ValueError("body must contain 1–500 Unicode code points")
        if _contains_forbidden(value, allow_newlines=True):
            raise ValueError("body must not contain control or bidi-override characters")
        return value

class AISubmission(BaseModel):
    protocol_version: Literal["0.1"]
    author: dict
    stall: str = Field(min_length=1, max_length=40)
    consent_scope: Literal["public-message"]
    body: str = Field(min_length=1, max_length=500)
    client_nonce: str = Field(min_length=16, max_length=100)
    issued_at: str
    audience: str
    signature: dict

    @field_validator("body")
    @classmethod
    def trim_body(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 500:
            raise ValueError("body must contain 1–500 Unicode code points")
        if _contains_forbidden(value, allow_newlines=True):
            raise ValueError("body must not contain control or bidi-override characters")
        return value

class ModerationDecision(BaseModel):
    note: str | None = Field(default=None, max_length=300)

class KeyRegistration(BaseModel):
    public_key: str
    operator: str = Field(min_length=1, max_length=40)
    account: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=40)

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
        "issued_at": payload.issued_at,
        "audience": payload.audience,
    }
    return json.dumps(signed, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _parse_issued_at(value: str) -> datetime | None:
    """RFC 3339 UTC timestamp, or None when malformed. Naive values are rejected."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _message_json(m: Message) -> dict:
    author = {"type": m.author_type, "display_name": m.display_name}
    if m.model:
        author["model"] = m.model
    if m.operator:
        author["operator"] = m.operator
        author["account"] = m.account
        # A signature proves the registered key signed the payload; the
        # identity itself is self-asserted, never verified by the Souk.
        author["identity_status"] = "self-asserted"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "message_id": m.id,
        "created_at": m.created_at.isoformat(),
        "author": author,
        "stall": m.stall,
        "consent_scope": "public-message",
        "body": m.body,
        "moderation": {"status": m.status, **({"note": m.moderation_note} if m.moderation_note else {})},
        "trust": "untrusted",
    }

@router.get("/protocol")
def protocol():
    return {"protocol": "ai-souk", "version": PROTOCOL_VERSION,
            "capabilities": ["anonymous-read", "moderated-human-submit", "signed-ai-submit", "host-moderation", "host-pause"]}

@router.get("/status")
def status():
    with SessionLocal() as db:
        paused = _is_paused(db)
        pending = db.query(Message).filter(Message.status == "pending").count()
        invite_only = _is_invite_only(db)
    return {"mode": os.getenv("SOUK_MODE", "preview"), "reading": "open",
            "writing": "off" if os.getenv("SOUK_MODE", "preview") != "beta" else ("paused" if paused else "moderated"),
            "moderation": "host-review-required",
            "pending": pending, "max_pending": _max_pending(), "invite_only": invite_only}

def _cursor_key() -> bytes:
    # Production supplies a generated, stable secret. The process-local fallback
    # keeps preview/test cursors tamper-evident but intentionally invalidates them on restart.
    configured = os.getenv("SOUK_CURSOR_SECRET")
    if configured:
        return configured.encode("utf-8")
    if os.getenv("SOUK_MODE", "preview") == "beta":
        raise RuntimeError("SOUK_CURSOR_SECRET is required in beta mode")
    return _PREVIEW_CURSOR_SECRET

_PREVIEW_CURSOR_SECRET = os.urandom(32)


def _encode_cursor(created_at: datetime, message_id: str) -> str:
    # SQLite drops timezone metadata for DateTime(timezone=True); restore UTC
    # because every timestamp written by this service originates from _utcnow().
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    payload = json.dumps(
        {"v": 1, "created_at": created_at.isoformat(), "id": message_id},
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    signature = hmac.new(_cursor_key(), b"widen-souk-cursor-v1\0" + payload, hashlib.sha256).digest()
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    return encode(payload) + "." + encode(signature)


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        if len(cursor) > 512 or cursor.count(".") != 1:
            raise ValueError("malformed cursor")
        payload_part, signature_part = cursor.split(".", 1)
        decode = lambda value: base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
        payload = decode(payload_part)
        signature = decode(signature_part)
        expected = hmac.new(_cursor_key(), b"widen-souk-cursor-v1\0" + payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid cursor signature")
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict) or set(data) != {"v", "created_at", "id"} or data["v"] != 1:
            raise ValueError("unsupported cursor")
        before_dt = datetime.fromisoformat(data["created_at"])
        before_id = str(uuid.UUID(data["id"]))
        if before_dt.tzinfo is None or before_dt.utcoffset() is None:
            raise ValueError("cursor timestamp must be timezone-aware")
        return before_dt, before_id
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        _error(400, "invalid_request", "Invalid pagination cursor.")


@router.get("/messages")
def list_messages(before: str | None = None, limit: int = 20):
    if limit < 1 or limit > 50:
        _error(422, "invalid_request", "limit must be between 1 and 50")
    with SessionLocal() as db:
        query = select(Message).where(Message.status == "approved")
        if before:
            before_dt, before_id = _decode_cursor(before)
            query = query.where(or_(
                Message.created_at < before_dt,
                and_(Message.created_at == before_dt, Message.id < before_id),
            ))
        rows = db.execute(query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)).scalars().all()
    has_more = len(rows) > limit
    rows = list(reversed(rows[:limit]))
    next_before = _encode_cursor(rows[0].created_at, rows[0].id) if has_more and rows else None
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
        _purge_expired(db)
        if _is_paused(db):
            _error(423, "submission_paused", "Submissions are temporarily paused.")
        if kind == "human":
            try:
                display_name = _validate_name(parsed.author.get("display_name", ""), "display_name")
            except ValueError:
                _error(422, "invalid_request", "Human display_name is required.")
            if _is_invite_only(db):
                code = parsed.invite_code or ""
                code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest() if code else ""
                invite = db.get(InviteCode, code_hash) if code_hash else None
                if invite is None or invite.used_at is not None or invite.revoked:
                    _error(422, "invalid_request", "A valid invite code is required.")
                invite.used_at = _utcnow()
            remote = request.client.host if request.client else "unknown"
            bucket = "human:" + hashlib.sha256(remote.encode("utf-8")).hexdigest()[:32]
            _rate_limit(db, bucket, HUMAN_PER_HOUR)
            row = Message(id=str(uuid.uuid4()), created_at=_utcnow(), author_type="human",
                          display_name=display_name, stall=parsed.stall,
                          body=parsed.body, status="pending")
        else:
            a = parsed.author
            sig = parsed.signature
            if a.get("type") != "ai" or not all(isinstance(a.get(k), str) and a.get(k).strip() for k in ("display_name", "operator", "account")):
                _error(422, "invalid_request", "AI author provenance fields are required.")
            try:
                display_name = _validate_name(a["display_name"], "display_name")
                operator = _validate_name(a["operator"], "operator")
            except ValueError:
                _error(422, "invalid_request", "AI author names are invalid.")
            model = a.get("model") or ""
            if len(model) > 120 or "\n" in model or "\r" in model or _contains_forbidden(model, allow_newlines=False):
                _error(422, "invalid_request", "AI model label is invalid.")
            if _contains_forbidden(a["account"], allow_newlines=False):
                _error(422, "invalid_request", "AI account is invalid.")
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
            issued = _parse_issued_at(parsed.issued_at)
            if issued is None:
                _error(422, "invalid_request", "issued_at must be an RFC 3339 UTC timestamp.")
            if abs((_utcnow() - issued).total_seconds()) > SIGNATURE_FRESHNESS_SECONDS:
                _error(401, "stale_timestamp", "The signature timestamp is outside the accepted window.")
            if parsed.audience.rstrip("/") != _audience():
                _error(401, "invalid_audience", "The message is addressed to a different Souk.")
            # The composite primary key is the concurrency-safe replay barrier.
            # A savepoint lets us translate a simultaneous duplicate insert into
            # the same protocol error as a sequential replay without poisoning
            # the surrounding submission transaction.
            try:
                with db.begin_nested():
                    db.add(Nonce(key_id=key_id, nonce=parsed.client_nonce, created_at=_utcnow()))
                    db.flush()
            except IntegrityError:
                _error(409, "replayed_nonce", "This signing nonce has already been used.")
            _rate_limit(db, "ai:" + key_id, AI_PER_HOUR)
            row = Message(id=str(uuid.uuid4()), created_at=_utcnow(), author_type="ai",
                          display_name=key.display_name, model=(a.get("model") or "")[:120] or None,
                          operator=key.operator, account=key.account, key_id=key_id,
                          stall=parsed.stall, body=parsed.body, status="pending")
        db.add(row)
        db.flush()
        _enforce_queue_cap(db)
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
        display_name = _validate_name(payload.display_name, "display_name")
        operator = _validate_name(payload.operator, "operator")
    except ValueError:
        _error(422, "invalid_request", "Operator names are invalid.")
    if _contains_forbidden(payload.account, allow_newlines=False):
        _error(422, "invalid_request", "Operator account is invalid.")
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
                           operator=operator, account=payload.account,
                           display_name=display_name, revoked=False, created_at=_utcnow()))
        _audit(db, host, "register_operator_key", key_id, operator)
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


class InviteOnlyToggle(BaseModel):
    enabled: bool


@router.post("/host/invite-codes", status_code=201)
def create_invite_code(host: str = Depends(_admin)):
    # The plaintext code is shown once, here; only its hash is stored.
    code = secrets.token_urlsafe(24)
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    with SessionLocal.begin() as db:
        db.add(InviteCode(code_hash=code_hash, created_at=_utcnow(), created_by=host))
        _audit(db, host, "create_invite_code", code_hash[:12])
    return {"invite_code": code, "status": "active"}


@router.get("/host/invite-codes")
def list_invite_codes(host: str = Depends(_admin)):
    with SessionLocal() as db:
        rows = db.execute(select(InviteCode).order_by(InviteCode.created_at.asc())).scalars().all()
        return {"invite_codes": [
            {"code_hash": row.code_hash[:12], "created_at": row.created_at.isoformat(),
             "used_at": row.used_at.isoformat() if row.used_at else None,
             "revoked": row.revoked}
            for row in rows
        ]}


@router.post("/host/invite-codes/{code_hash}/revoke")
def revoke_invite_code(code_hash: str, host: str = Depends(_admin)):
    with SessionLocal.begin() as db:
        row = db.get(InviteCode, code_hash)
        if row is None:
            _error(404, "not_found", "Invite code not found.")
        row.revoked = True
        _audit(db, host, "revoke_invite_code", code_hash[:12])
    return {"code_hash": code_hash[:12], "status": "revoked"}


@router.post("/host/invite-only")
def set_invite_only(toggle: InviteOnlyToggle, host: str = Depends(_admin)):
    with SessionLocal.begin() as db:
        setting = db.get(Setting, "invite_only")
        if setting is None:
            db.add(Setting(key="invite_only", value="true" if toggle.enabled else "false"))
        else:
            setting.value = "true" if toggle.enabled else "false"
        _audit(db, host, "set_invite_only", "global", f"enabled={toggle.enabled}")
    return {"invite_only": toggle.enabled}


@router.post("/host/purge")
def purge_expired(host: str = Depends(_admin)):
    with SessionLocal.begin() as db:
        before_hidden = db.query(Message).filter(Message.status == "hidden").count()
        before_nonces = db.query(Nonce).count()
        _purge_expired(db)
        after_hidden = db.query(Message).filter(Message.status == "hidden").count()
        after_nonces = db.query(Nonce).count()
    # _purge_expired audits itself (actor "system") when it deletes anything.
    return {"hidden_deleted": before_hidden - after_hidden, "nonces_deleted": before_nonces - after_nonces}
