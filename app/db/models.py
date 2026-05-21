from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CustomerModel(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(30), nullable=False, default="en")
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )

    loans: Mapped[list["LoanModel"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    sessions: Mapped[list["CallSessionModel"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class LoanModel(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)

    loan_amount: Mapped[float] = mapped_column(Float, nullable=False)
    due_date: Mapped[str] = mapped_column(String(30), nullable=False)
    overdue_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    late_fee: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )

    customer: Mapped[CustomerModel] = relationship(back_populates="loans")
    sessions: Mapped[list["CallSessionModel"]] = relationship(back_populates="loan")


class CallSessionModel(Base):
    __tablename__ = "call_sessions"

    session_id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)

    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    loan_id: Mapped[int | None] = mapped_column(ForeignKey("loans.id"), nullable=True)

    phase: Mapped[str] = mapped_column(String(60), nullable=False)
    language: Mapped[str] = mapped_column(String(30), nullable=False)

    identity_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    identity_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    turn_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    last_intent: Mapped[str] = mapped_column(String(80), nullable=False)
    last_user_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_agent_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False, default="low")
    frustration_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    payment_status: Mapped[str] = mapped_column(String(60), nullable=False, default="not_initiated")
    commitment_received: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    commitment_time: Mapped[str | None] = mapped_column(String(120), nullable=True)
    commitment_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    complaint_registered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dispute_registered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    kyc_request_registered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    escalation_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    escalation_offered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    outcome: Mapped[str | None] = mapped_column(String(120), nullable=True)
    outcome_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    pending_action: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pending_action_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )

    customer: Mapped[CustomerModel | None] = relationship(back_populates="sessions")
    loan: Mapped[LoanModel | None] = relationship(back_populates="sessions")

    turns: Mapped[list["ConversationTurnModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )

    traces: Mapped[list["DecisionTraceModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ConversationTurnModel(Base):
    __tablename__ = "conversation_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("call_sessions.session_id"), index=True)

    turn_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    session: Mapped[CallSessionModel] = relationship(back_populates="turns")


class DecisionTraceModel(Base):
    __tablename__ = "decision_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("call_sessions.session_id"), index=True)

    trace_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    session: Mapped[CallSessionModel] = relationship(back_populates="traces")