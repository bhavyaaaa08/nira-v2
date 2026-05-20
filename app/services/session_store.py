from __future__ import annotations

from typing import Dict, List, Optional

from app.core.enums import CallPhase, Language
from app.core.schemas import CustomerProfile, LoanAccount
from app.core.state import CallState


class SessionStore:
    """
    Temporary in-memory session store for NIRA v2.

    This will later be replaced or backed by SQLite/PostgreSQL.
    For now, it lets the FastAPI backend create sessions and process turns.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, CallState] = {}

    def create_session(
        self,
        customer_name: str,
        phone: str,
        loan_amount: float,
        due_date: str,
        overdue_days: int = 0,
        late_fee: float | None = None,
        preferred_language: Language = Language.ENGLISH,
    ) -> CallState:
        state = CallState()
        state.phase = CallPhase.GREETING
        state.customer = CustomerProfile(
            customer_id=len(self._sessions) + 1,
            name=customer_name,
            phone=phone,
            preferred_language=preferred_language,
            is_verified=False,
        )
        state.loan = LoanAccount(
            loan_id=len(self._sessions) + 1,
            customer_id=state.customer.customer_id,
            loan_amount=loan_amount,
            due_date=due_date,
            overdue_days=overdue_days,
            status="active",
            late_fee=late_fee,
        )
        state.language = preferred_language

        self._sessions[state.session_id] = state
        return state

    def get_session(self, session_id: str) -> Optional[CallState]:
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[CallState]:
        return list(self._sessions.values())

    def delete_session(self, session_id: str) -> bool:
        if session_id not in self._sessions:
            return False

        del self._sessions[session_id]
        return True

    def clear(self) -> None:
        self._sessions.clear()


def serialize_state(state: CallState) -> dict:
    return {
        "session_id": state.session_id,
        "phase": state.phase.value,
        "identity_verified": state.identity_verified,
        "identity_attempts": state.identity_attempts,
        "language": state.language.value,
        "turn_number": state.turn_number,
        "risk_score": state.risk_score,
        "risk_level": state.risk_level.value,
        "payment_status": state.payment_status.value,
        "commitment_received": state.commitment_received,
        "commitment_time": state.commitment_time,
        "complaint_registered": state.complaint_registered,
        "dispute_registered": state.dispute_registered,
        "kyc_request_registered": state.kyc_request_registered,
        "escalation_required": state.escalation_required,
        "outcome": state.outcome,
        "outcome_detail": state.outcome_detail,
        "duration_seconds": state.duration_seconds,
        "customer": {
            "customer_id": state.customer.customer_id if state.customer else None,
            "name": state.customer.name if state.customer else None,
            "phone": state.customer.phone if state.customer else None,
            "preferred_language": (
                state.customer.preferred_language.value if state.customer else None
            ),
            "is_verified": state.customer.is_verified if state.customer else False,
        },
        "loan": {
            "loan_id": state.loan.loan_id if state.loan else None,
            "loan_amount": state.loan.loan_amount if state.loan else None,
            "due_date": state.loan.due_date if state.loan else None,
            "overdue_days": state.loan.overdue_days if state.loan else None,
            "status": state.loan.status if state.loan else None,
            "late_fee": state.loan.late_fee if state.loan else None,
        },
        "conversation": [
            {
                "role": turn.role,
                "content": turn.content,
                "timestamp": turn.timestamp.isoformat(),
                "metadata": turn.metadata,
            }
            for turn in state.conversation
        ],
        "decision_trace": state.decision_trace,
    }


session_store = SessionStore()