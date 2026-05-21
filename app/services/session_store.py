from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.enums import (
    CallPhase,
    Intent,
    Language,
    PaymentStatus,
    RiskLevel,
)
from app.core.schemas import CustomerProfile, LoanAccount
from app.core.state import CallState
from app.db.repositories import NiraRepository


def _enum_value(value: Any) -> Any:
    if value is None:
        return None

    if hasattr(value, "value"):
        return value.value

    return value


def _datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def serialize_state(state: CallState) -> dict:
    customer = None
    if state.customer:
        customer = {
            "customer_id": state.customer.customer_id,
            "name": state.customer.name,
            "phone": state.customer.phone,
            "preferred_language": _enum_value(state.customer.preferred_language),
            "is_verified": state.customer.is_verified,
        }

    loan = None
    if state.loan:
        loan = {
            "loan_id": state.loan.loan_id,
            "customer_id": state.loan.customer_id,
            "loan_amount": state.loan.loan_amount,
            "due_date": state.loan.due_date,
            "overdue_days": state.loan.overdue_days,
            "status": state.loan.status,
            "late_fee": state.loan.late_fee,
        }

    pending_action = getattr(state, "pending_action", None)
    pending_action_data = getattr(state, "pending_action_data", {})

    return {
        "session_id": state.session_id,
        "phase": _enum_value(state.phase),
        "customer": customer,
        "loan": loan,
        "language": _enum_value(state.language),
        "identity_verified": state.identity_verified,
        "identity_attempts": state.identity_attempts,
        "turn_number": state.turn_number,
        "started_at": _datetime_value(state.started_at),
        "ended_at": _datetime_value(state.ended_at),
        "duration_seconds": state.duration_seconds,
        "last_intent": _enum_value(state.last_intent),
        "last_user_text": state.last_user_text,
        "last_agent_response": state.last_agent_response,
        "risk_score": state.risk_score,
        "risk_level": _enum_value(state.risk_level),
        "frustration_score": state.frustration_score,
        "payment_status": _enum_value(state.payment_status),
        "commitment_received": state.commitment_received,
        "commitment_time": state.commitment_time,
        "commitment_amount": state.commitment_amount,
        "complaint_registered": state.complaint_registered,
        "dispute_registered": state.dispute_registered,
        "kyc_request_registered": state.kyc_request_registered,
        "escalation_required": state.escalation_required,
        "escalation_offered": state.escalation_offered,
        "outcome": state.outcome,
        "outcome_detail": state.outcome_detail,
        "pending_action": _enum_value(pending_action),
        "pending_action_data": pending_action_data,
        "conversation": [
            {
                "role": turn.role,
                "content": turn.content,
                "timestamp": _datetime_value(turn.timestamp),
                "metadata": turn.metadata,
            }
            for turn in state.conversation
        ],
        "decision_trace": state.decision_trace,
    }


class SessionStore:
    """
    Runtime session cache + SQLite persistence.

    Active sessions stay in memory for fast turn processing.
    Every state snapshot is also saved to SQLite.
    If FastAPI restarts, get/list can reconstruct sessions from SQLite.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, CallState] = {}
        self.repository = NiraRepository()

    def create_session(
        self,
        customer_name: str,
        phone: str,
        loan_amount: float,
        due_date: str,
        overdue_days: int,
        late_fee: float | None = None,
        preferred_language: Language = Language.ENGLISH,
    ) -> CallState:
        state = CallState(
            phase=CallPhase.GREETING,
            language=preferred_language,
        )

        state.customer = CustomerProfile(
            name=customer_name,
            phone=phone,
            preferred_language=preferred_language,
            is_verified=False,
        )

        state.loan = LoanAccount(
            loan_amount=loan_amount,
            due_date=due_date,
            overdue_days=overdue_days,
            status="active",
            late_fee=late_fee,
        )

        state.identity_verified = False
        state.identity_attempts = 0
        state.last_intent = Intent.UNKNOWN
        state.risk_level = RiskLevel.LOW
        state.payment_status = PaymentStatus.NOT_INITIATED

        self._sessions[state.session_id] = state
        self.repository.save_state(state)

        return state

    def get_session(self, session_id: str) -> CallState | None:
        if session_id in self._sessions:
            return self._sessions[session_id]

        state = self.repository.load_state(session_id)

        if state:
            self._sessions[session_id] = state

        return state

    def list_sessions(self) -> list[CallState]:
        db_states = self.repository.list_states()

        for state in db_states:
            self._sessions[state.session_id] = state

        cached_only = [
            state
            for session_id, state in self._sessions.items()
            if session_id not in {db_state.session_id for db_state in db_states}
        ]

        return db_states + cached_only

    def save_session(self, state: CallState) -> None:
        self._sessions[state.session_id] = state
        self.repository.save_state(state)

    def delete_session(self, session_id: str) -> bool:
        existed_in_memory = session_id in self._sessions
        self._sessions.pop(session_id, None)

        deleted_from_db = self.repository.delete_session(session_id)

        return existed_in_memory or deleted_from_db

    def clear_memory_cache(self) -> None:
        self._sessions.clear()


session_store = SessionStore()