import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Novo Agente")
    config_json: Mapped[Any] = mapped_column(JSON, nullable=False, default=dict)
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    exports: Mapped[list["AgentExport"]] = relationship("AgentExport", back_populates="agent")
    payment_intents: Mapped[list["PaymentIntent"]] = relationship(
        "PaymentIntent", back_populates="agent", foreign_keys="PaymentIntent.agent_id"
    )

    def __repr__(self) -> str:
        return f"<Agent id={self.id} name={self.name!r}>"


class AgentExport(Base):
    __tablename__ = "agent_exports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    download_token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    agent: Mapped["Agent"] = relationship("Agent", back_populates="exports")

    def __repr__(self) -> str:
        return f"<AgentExport id={self.id} agent_id={self.agent_id}>"


class PaymentIntent(Base):
    __tablename__ = "payment_intents"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # Stripe PI ID
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="brl")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    agent: Mapped["Agent | None"] = relationship(
        "Agent", back_populates="payment_intents", foreign_keys=[agent_id]
    )

    def __repr__(self) -> str:
        return f"<PaymentIntent id={self.id} status={self.status}>"
