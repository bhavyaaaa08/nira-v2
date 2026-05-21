from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.orchestrator_agent import OrchestratorAgent
from app.core.enums import Language
from app.services.session_store import serialize_state, session_store


router = APIRouter(prefix="/api/calls", tags=["calls"])
orchestrator = OrchestratorAgent()


class CreateSessionRequest(BaseModel):
    customer_name: str = "Anita Verma"
    phone: str = "9876543210"
    loan_amount: float = 50000
    due_date: str = "2026-05-01"
    overdue_days: int = 8
    late_fee: float | None = 500
    preferred_language: Language = Language.ENGLISH


class UserTurnRequest(BaseModel):
    user_text: str = Field(..., min_length=1)
    channel: str = "text"


@router.post("/sessions")
def create_call_session(payload: CreateSessionRequest) -> dict:
    state = session_store.create_session(
        customer_name=payload.customer_name,
        phone=payload.phone,
        loan_amount=payload.loan_amount,
        due_date=payload.due_date,
        overdue_days=payload.overdue_days,
        late_fee=payload.late_fee,
        preferred_language=payload.preferred_language,
    )

    return {
        "message": "session_created",
        "session": serialize_state(state),
        "next_step": (
            f"Ask the customer: Hello, I am NIRA calling from Accure regarding "
            f"your banking account. Am I speaking with {payload.customer_name}?"
        ),
    }


@router.get("/sessions")
def list_call_sessions() -> dict:
    sessions = session_store.list_sessions()

    return {
        "count": len(sessions),
        "sessions": [serialize_state(session) for session in sessions],
    }


@router.get("/sessions/{session_id}")
def get_call_session(session_id: str) -> dict:
    state = session_store.get_session(session_id)

    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session": serialize_state(state),
    }


@router.post("/sessions/{session_id}/turns")
def process_call_turn(session_id: str, payload: UserTurnRequest) -> dict:
    state = session_store.get_session(session_id)

    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    result = orchestrator.process_turn(
        state=state,
        user_text=payload.user_text,
        channel=payload.channel,
    )

    session_store.save_session(state)

    return {
        "message": "turn_processed",
        "result": result.model_dump(mode="json"),
        "session": serialize_state(state),
    }


@router.get("/sessions/{session_id}/trace")
def get_decision_trace(session_id: str) -> dict:
    state = session_store.get_session(session_id)

    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": state.session_id,
        "trace_count": len(state.decision_trace),
        "decision_trace": state.decision_trace,
    }


@router.delete("/sessions/{session_id}")
def delete_call_session(session_id: str) -> dict:
    deleted = session_store.delete_session(session_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "message": "session_deleted",
        "session_id": session_id,
    }