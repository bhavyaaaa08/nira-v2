from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.operations_store import operations_store


router = APIRouter(prefix="/api/operations", tags=["operations"])


@router.get("/tickets")
def list_tickets(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    return {
        "tickets": operations_store.list_tickets(limit=limit),
    }


@router.get("/commitments")
def list_payment_commitments(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    return {
        "payment_commitments": operations_store.list_payment_commitments(limit=limit),
    }


@router.get("/voice-interactions")
def list_voice_interactions(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    return {
        "voice_interactions": operations_store.list_voice_interactions(limit=limit),
    }


@router.get("/sessions/{session_id}")
def get_session_operations(session_id: str) -> dict:
    return operations_store.get_session_operations(session_id)