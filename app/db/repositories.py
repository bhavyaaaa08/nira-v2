from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.enums import (
    CallPhase,
    Intent,
    Language,
    PaymentStatus,
    PendingAction,
    RiskLevel,
)
from app.core.schemas import CustomerProfile, LoanAccount
from app.core.state import CallState, ConversationTurn
from app.db.database import db_session
from app.db.models import (
    CallSessionModel,
    ConversationTurnModel,
    CustomerModel,
    DecisionTraceModel,
    LoanModel,
)


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None

    if hasattr(value, "value"):
        return value.value

    return str(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value or {}, default=str, ensure_ascii=False)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.now()

    return datetime.now()


class NiraRepository:
    """
    SQLite persistence layer for NIRA call state.

    Current design:
    - SessionStore still keeps active sessions in memory for speed.
    - This repository persists every session snapshot to SQLite.
    - If FastAPI restarts, SessionStore can reconstruct CallState from SQLite.
    """

    def upsert_customer(self, state: CallState) -> int | None:
        if not state.customer:
            return None

        with db_session() as db:
            customer = db.scalar(
                select(CustomerModel).where(CustomerModel.phone == state.customer.phone)
            )

            if customer is None:
                customer = CustomerModel(
                    name=state.customer.name,
                    phone=state.customer.phone,
                    preferred_language=_enum_value(state.customer.preferred_language) or "en",
                    is_verified=state.customer.is_verified,
                )
                db.add(customer)
                db.flush()
            else:
                customer.name = state.customer.name
                customer.preferred_language = _enum_value(state.customer.preferred_language) or "en"
                customer.is_verified = state.customer.is_verified

            state.customer.customer_id = customer.id
            return customer.id

    def upsert_loan(self, state: CallState, customer_id: int | None) -> int | None:
        if not state.loan or customer_id is None:
            return None

        with db_session() as db:
            loan = None

            if state.loan.loan_id:
                loan = db.get(LoanModel, state.loan.loan_id)

            if loan is None:
                loan = LoanModel(
                    customer_id=customer_id,
                    loan_amount=state.loan.loan_amount,
                    due_date=state.loan.due_date,
                    overdue_days=state.loan.overdue_days,
                    status=state.loan.status,
                    late_fee=state.loan.late_fee,
                )
                db.add(loan)
                db.flush()
            else:
                loan.customer_id = customer_id
                loan.loan_amount = state.loan.loan_amount
                loan.due_date = state.loan.due_date
                loan.overdue_days = state.loan.overdue_days
                loan.status = state.loan.status
                loan.late_fee = state.loan.late_fee

            state.loan.loan_id = loan.id
            state.loan.customer_id = customer_id
            return loan.id

    def save_state(self, state: CallState) -> None:
        customer_id = self.upsert_customer(state)
        loan_id = self.upsert_loan(state, customer_id)

        with db_session() as db:
            session = db.get(CallSessionModel, state.session_id)

            pending_action = getattr(state, "pending_action", None)
            pending_action_data = getattr(state, "pending_action_data", {})

            if session is None:
                session = CallSessionModel(
                    session_id=state.session_id,
                    customer_id=customer_id,
                    loan_id=loan_id,
                    phase=_enum_value(state.phase) or CallPhase.PRE_CALL.value,
                    language=_enum_value(state.language) or Language.ENGLISH.value,
                    started_at=state.started_at,
                    last_intent=_enum_value(state.last_intent) or Intent.UNKNOWN.value,
                    risk_level=_enum_value(state.risk_level) or RiskLevel.LOW.value,
                    payment_status=_enum_value(state.payment_status)
                    or PaymentStatus.NOT_INITIATED.value,
                )
                db.add(session)

            session.customer_id = customer_id
            session.loan_id = loan_id

            session.phase = _enum_value(state.phase) or CallPhase.PRE_CALL.value
            session.language = _enum_value(state.language) or Language.ENGLISH.value

            session.identity_verified = state.identity_verified
            session.identity_attempts = state.identity_attempts

            session.turn_number = state.turn_number
            session.started_at = state.started_at
            session.ended_at = state.ended_at

            session.last_intent = _enum_value(state.last_intent) or Intent.UNKNOWN.value
            session.last_user_text = state.last_user_text
            session.last_agent_response = state.last_agent_response

            session.risk_score = state.risk_score
            session.risk_level = _enum_value(state.risk_level) or RiskLevel.LOW.value
            session.frustration_score = state.frustration_score

            session.payment_status = (
                _enum_value(state.payment_status) or PaymentStatus.NOT_INITIATED.value
            )
            session.commitment_received = state.commitment_received
            session.commitment_time = state.commitment_time
            session.commitment_amount = state.commitment_amount

            session.complaint_registered = state.complaint_registered
            session.dispute_registered = state.dispute_registered
            session.kyc_request_registered = state.kyc_request_registered
            session.escalation_required = state.escalation_required
            session.escalation_offered = state.escalation_offered

            session.outcome = state.outcome
            session.outcome_detail = state.outcome_detail

            session.pending_action = _enum_value(pending_action)
            session.pending_action_data_json = _json_dumps(pending_action_data)

            session.updated_at = datetime.now()

            db.query(ConversationTurnModel).filter(
                ConversationTurnModel.session_id == state.session_id
            ).delete()

            for index, turn in enumerate(state.conversation, start=1):
                db.add(
                    ConversationTurnModel(
                        session_id=state.session_id,
                        turn_index=index,
                        role=turn.role,
                        content=turn.content,
                        metadata_json=_json_dumps(turn.metadata),
                        created_at=turn.timestamp,
                    )
                )

            db.query(DecisionTraceModel).filter(
                DecisionTraceModel.session_id == state.session_id
            ).delete()

            for index, trace in enumerate(state.decision_trace, start=1):
                db.add(
                    DecisionTraceModel(
                        session_id=state.session_id,
                        trace_index=index,
                        payload_json=_json_dumps(trace),
                        created_at=_parse_datetime(trace.get("timestamp")),
                    )
                )

    def load_state(self, session_id: str) -> CallState | None:
        with db_session() as db:
            session = db.get(CallSessionModel, session_id)

            if session is None:
                return None

            customer = db.get(CustomerModel, session.customer_id) if session.customer_id else None
            loan = db.get(LoanModel, session.loan_id) if session.loan_id else None

            state = CallState(session_id=session.session_id)

            state.phase = CallPhase(session.phase)
            state.language = Language(session.language)
            state.identity_verified = session.identity_verified
            state.identity_attempts = session.identity_attempts

            state.turn_number = session.turn_number
            state.started_at = session.started_at
            state.ended_at = session.ended_at

            state.last_intent = Intent(session.last_intent)
            state.last_user_text = session.last_user_text
            state.last_agent_response = session.last_agent_response

            state.risk_score = session.risk_score
            state.risk_level = RiskLevel(session.risk_level)
            state.frustration_score = session.frustration_score

            state.payment_status = PaymentStatus(session.payment_status)
            state.commitment_received = session.commitment_received
            state.commitment_time = session.commitment_time
            state.commitment_amount = session.commitment_amount

            state.complaint_registered = session.complaint_registered
            state.dispute_registered = session.dispute_registered
            state.kyc_request_registered = session.kyc_request_registered
            state.escalation_required = session.escalation_required
            state.escalation_offered = session.escalation_offered

            state.outcome = session.outcome
            state.outcome_detail = session.outcome_detail

            if hasattr(state, "pending_action"):
                state.pending_action = (
                    PendingAction(session.pending_action)
                    if session.pending_action
                    else None
                )
                state.pending_action_data = _json_loads(
                    session.pending_action_data_json,
                    {},
                )

            if customer:
                state.customer = CustomerProfile(
                    customer_id=customer.id,
                    name=customer.name,
                    phone=customer.phone,
                    preferred_language=Language(customer.preferred_language),
                    is_verified=customer.is_verified,
                )

            if loan:
                state.loan = LoanAccount(
                    loan_id=loan.id,
                    customer_id=loan.customer_id,
                    loan_amount=loan.loan_amount,
                    due_date=loan.due_date,
                    overdue_days=loan.overdue_days,
                    status=loan.status,
                    late_fee=loan.late_fee,
                )

            turns = (
                db.query(ConversationTurnModel)
                .filter(ConversationTurnModel.session_id == session_id)
                .order_by(ConversationTurnModel.turn_index.asc())
                .all()
            )

            state.conversation = [
                ConversationTurn(
                    role=turn.role,
                    content=turn.content,
                    timestamp=turn.created_at,
                    metadata=_json_loads(turn.metadata_json, {}),
                )
                for turn in turns
            ]

            traces = (
                db.query(DecisionTraceModel)
                .filter(DecisionTraceModel.session_id == session_id)
                .order_by(DecisionTraceModel.trace_index.asc())
                .all()
            )

            state.decision_trace = [
                _json_loads(trace.payload_json, {})
                for trace in traces
            ]

            return state

    def list_states(self) -> list[CallState]:
        with db_session() as db:
            rows = (
                db.query(CallSessionModel.session_id)
                .order_by(CallSessionModel.updated_at.desc())
                .all()
            )

        states: list[CallState] = []

        for row in rows:
            state = self.load_state(row.session_id)
            if state:
                states.append(state)

        return states

    def delete_session(self, session_id: str) -> bool:
        with db_session() as db:
            session = db.get(CallSessionModel, session_id)

            if session is None:
                return False

            db.delete(session)
            return True