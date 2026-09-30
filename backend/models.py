from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    source: Mapped[str] = mapped_column(String, default="demo")
    source_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    contact: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="New")
    interest_level: Mapped[str] = mapped_column(String, default="Medium")
    notes: Mapped[str] = mapped_column(Text, default="")
    deal_context: Mapped[str] = mapped_column(Text, default="")
    last_interaction: Mapped[str | None] = mapped_column(String, nullable=True)
    next_followup: Mapped[str | None] = mapped_column(String, nullable=True)
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    replied: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), index=True)
    action: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    sources: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String, default="pending")
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    approved_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_recipient: Mapped[str | None] = mapped_column(String, nullable=True)
    model_id: Mapped[str] = mapped_column(String, default="rules-demo-v1")
    experiment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    variant_id: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String, default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"), nullable=True, index=True)
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SendAttempt(Base):
    __tablename__ = "send_attempts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendations.id"), unique=True)
    recipient: Mapped[str] = mapped_column(String)
    draft_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="reserved")
    provider_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Connection(Base):
    __tablename__ = "connections"
    provider: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="disconnected")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_count: Mapped[int] = mapped_column(Integer, default=0)


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    config: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExperimentAssignment(Base):
    __tablename__ = "experiment_assignments"
    __table_args__ = (UniqueConstraint("experiment_id", "contact_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"))
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"))
    variant_id: Mapped[str] = mapped_column(String)
    exposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OAuthCredential(Base):
    __tablename__ = "oauth_credentials"
    provider: Mapped[str] = mapped_column(String, primary_key=True)
    encrypted_token: Mapped[str] = mapped_column(Text)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OAuthPending(Base):
    __tablename__ = "oauth_pending"
    state: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String)
    code_verifier: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
