from __future__ import annotations

import os
from typing import Any

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd
import requests
import streamlit as st
from app.services.tts_service import synthesize_speech_to_file


import os

st.caption(f"GCP creds: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
st.caption(f"GCP project: {os.environ.get('GOOGLE_CLOUD_PROJECT')}")


DEFAULT_API_BASE_URL = os.getenv("NIRA_API_BASE_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT = 15


# ─────────────────────────────────────────────
# Page setup
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="NIRA v2 Dashboard",
    page_icon="🎙️",
    layout="wide",
)


# ─────────────────────────────────────────────
# Session-state defaults
# ─────────────────────────────────────────────

def init_state() -> None:
    defaults = {
        "api_base_url": DEFAULT_API_BASE_URL,
        "active_session_id": None,
        "active_session": None,
        "last_result": None,
        "last_trace": None,
        "last_next_step": None,
        "last_error": None,
    }

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


init_state()


# ─────────────────────────────────────────────
# API helpers
# ─────────────────────────────────────────────

def api_url(path: str) -> str:
    base = st.session_state.api_base_url.rstrip("/")
    return f"{base}{path}"


def request_json(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    try:
        response = requests.request(
            method=method,
            url=api_url(path),
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Could not connect to the NIRA API. Start FastAPI with: "
            "uvicorn app.main:app --reload"
        ) from exc
    except requests.exceptions.HTTPError as exc:
        detail = ""
        try:
            detail = response.json().get("detail", "")
        except Exception:
            detail = response.text
        raise RuntimeError(f"API error {response.status_code}: {detail}") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Request failed: {exc}") from exc


def health_check() -> bool:
    try:
        request_json("GET", "/health")
        return True
    except Exception:
        return False


def create_session(payload: dict[str, Any]) -> None:
    data = request_json("POST", "/api/calls/sessions", json=payload)
    session = data.get("session", {})

    st.session_state.active_session_id = session.get("session_id")
    st.session_state.active_session = session
    st.session_state.last_result = None
    st.session_state.last_trace = None
    st.session_state.last_next_step = data.get("next_step")
    st.session_state.last_error = None


def refresh_session() -> None:
    session_id = st.session_state.active_session_id
    if not session_id:
        return

    data = request_json("GET", f"/api/calls/sessions/{session_id}")
    st.session_state.active_session = data.get("session")


def refresh_trace() -> None:
    session_id = st.session_state.active_session_id
    if not session_id:
        return

    data = request_json("GET", f"/api/calls/sessions/{session_id}/trace")
    st.session_state.last_trace = data


def process_turn(user_text: str) -> None:
    session_id = st.session_state.active_session_id
    if not session_id:
        raise RuntimeError("Create a call session before sending a customer message.")

    data = request_json(
        "POST",
        f"/api/calls/sessions/{session_id}/turns",
        json={"user_text": user_text, "channel": "text"},
    )

    st.session_state.last_result = data.get("result")
    st.session_state.active_session = data.get("session")
    refresh_trace()
    st.session_state.last_error = None


def delete_session() -> None:
    session_id = st.session_state.active_session_id
    if not session_id:
        return

    request_json("DELETE", f"/api/calls/sessions/{session_id}")
    clear_ui_state()


def clear_ui_state() -> None:
    st.session_state.active_session_id = None
    st.session_state.active_session = None
    st.session_state.last_result = None
    st.session_state.last_trace = None
    st.session_state.last_next_step = None
    st.session_state.last_error = None


# ─────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────

def value(data: dict[str, Any] | None, key: str, default: Any = "—") -> Any:
    if not data:
        return default
    item = data.get(key, default)
    return default if item is None else item


def nested(data: dict[str, Any] | None, *keys: str, default: Any = "—") -> Any:
    current: Any = data or {}
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def format_money(amount: Any) -> str:
    try:
        return f"₹{float(amount):,.0f}"
    except Exception:
        return "—"


def normalize_turn(turn: dict[str, Any]) -> tuple[str, str]:
    role = turn.get("role", "assistant")
    content = turn.get("content", "")
    return role, content


def latest_agent_name() -> str:
    result = st.session_state.last_result
    return nested(result, "agent_decision", "selected_agent")


def latest_intent() -> str:
    result = st.session_state.last_result
    return nested(result, "intent_result", "intent")


def latest_judge_score() -> Any:
    result = st.session_state.last_result
    return nested(result, "judge_result", "score")

def fetch_summary(api_base_url: str, session_id: str) -> dict | None:
    try:
        response = requests.get(
            f"{api_base_url}/api/calls/sessions/{session_id}/summary",
            timeout=10,
        )

        if response.status_code != 200:
            return None

        return response.json().get("summary")
    except requests.RequestException:
        return None


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────

with st.sidebar:
    st.title("NIRA v2")
    st.caption("Banking voice intelligence demo dashboard")

    st.text_input("FastAPI base URL", key="api_base_url")

    is_healthy = health_check()
    if is_healthy:
        st.success("API connected")
    else:
        st.error("API not reachable")

    st.divider()
    st.subheader("Create demo session")

    customer_name = st.text_input("Customer name", value="Anita Verma")
    phone = st.text_input("Phone", value="9876543210")
    loan_amount = st.number_input("Loan amount", min_value=0.0, value=50000.0, step=1000.0)
    due_date = st.text_input("Due date", value="2026-05-01")
    overdue_days = st.number_input("Overdue days", min_value=0, value=8, step=1)
    late_fee = st.number_input("Late fee", min_value=0.0, value=500.0, step=100.0)
    preferred_language = st.selectbox(
        "Preferred language",
        options=["en", "hi", "hinglish", "ta"],
        index=0,
    )

    create_clicked = st.button("Create new call session", type="primary", use_container_width=True)
    if create_clicked:
        try:
            create_session(
                {
                    "customer_name": customer_name,
                    "phone": phone,
                    "loan_amount": loan_amount,
                    "due_date": due_date,
                    "overdue_days": overdue_days,
                    "late_fee": late_fee,
                    "preferred_language": preferred_language,
                }
            )
            st.success("Session created")
            st.rerun()
        except RuntimeError as exc:
            st.session_state.last_error = str(exc)

    if st.session_state.active_session_id:
        st.caption(f"Active session: `{st.session_state.active_session_id}`")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Refresh", use_container_width=True):
                try:
                    refresh_session()
                    refresh_trace()
                    st.rerun()
                except RuntimeError as exc:
                    st.session_state.last_error = str(exc)
        with c2:
            if st.button("Delete", use_container_width=True):
                try:
                    delete_session()
                    st.rerun()
                except RuntimeError as exc:
                    st.session_state.last_error = str(exc)

    if st.button("Reset dashboard UI", use_container_width=True):
        clear_ui_state()
        st.rerun()

    st.divider()
    st.subheader("Demo customer lines")

    sample_messages = {
        "Verify identity": "Yes, I am Anita Verma speaking.",
        "Ask late fee": "Why is there a late fee?",
        "Promise to pay": "I will pay ₹50000 tomorrow by 6 PM.",
        "Already paid": "I already paid, transaction id is OKPAY123.",
        "Payment failed case": "I paid already, transaction id is FAIL123456.",
        "Complaint": "You people keep calling again and again. This is harassment.",
        "Fraud claim": "I never took this loan. This looks like fraud.",
        "KYC update": "I want to update my mobile number in KYC.",
        "Escalation": "Connect me to a human executive.",
    }

    for label, text in sample_messages.items():
        if st.button(label, use_container_width=True):
            try:
                process_turn(text)
                st.rerun()
            except RuntimeError as exc:
                st.session_state.last_error = str(exc)


# ─────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────

st.title("NIRA v2 Command Center")
st.caption("Realtime dashboard for the custom multi-agent banking operations backend")

if st.session_state.last_error:
    st.error(st.session_state.last_error)

if not st.session_state.active_session_id:
    st.info("Create a new call session from the sidebar to start the demo.")
    st.stop()

try:
    refresh_session()
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

session = st.session_state.active_session or {}
customer = session.get("customer") or {}
loan = session.get("loan") or {}
conversation = session.get("conversation") or []

# ─────────────────────────────────────────────
# Top summary cards
# ─────────────────────────────────────────────

st.subheader("Live call state")

card1, card2, card3, card4, card5 = st.columns(5)
card1.metric("Phase", value=session.get("phase", "—"))
card2.metric("Identity", value="verified" if session.get("identity_verified") else "not verified")
card3.metric("Risk", value=f"{session.get('risk_level', '—')} / {session.get('risk_score', 0)}")
card4.metric("Payment", value=session.get("payment_status", "—"))
card5.metric("Turns", value=session.get("turn_number", 0))

info1, info2, info3, info4 = st.columns(4)
info1.metric("Selected agent", latest_agent_name())
info2.metric("Detected intent", latest_intent())
info3.metric("Judge score", latest_judge_score())
info4.metric("Outcome", session.get("outcome") or "not decided")

st.divider()

# ─────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────

tab_chat, tab_voice, tab_trace, tab_summary, tab_customer, tab_raw = st.tabs(
    ["Conversation", "Voice Demo", "Decision trace", "Summary", "Customer + loan", "Raw JSON"]
)

with tab_voice:
    st.subheader("Voice Demo")
    st.caption("Manual transcript → NIRA response → GCP Text-to-Speech")

    voice_text = st.text_area(
        "Manual transcript",
        placeholder="Example: meri salary nahi aai hai",
        height=120,
    )

    tts_language = st.selectbox(
        "TTS language",
        options=["hi-IN", "en-IN", "ta-IN"],
        index=0,
    )

    voice_map = {
        "hi-IN": "hi-IN-Wavenet-C",
        "en-IN": "en-IN-Wavenet-D",
        "ta-IN": "ta-IN-Wavenet-C",
    }

    if st.button("Send to NIRA and play voice reply", type="primary"):
        if not voice_text.strip():
            st.warning("Please enter a transcript first.")
        else:
            try:
                process_turn(voice_text.strip())

                final_response = nested(
                    st.session_state.last_result,
                    "final_response",
                    default="",
                )

                if not final_response:
                    st.warning("No NIRA response received.")
                    st.stop()

                st.markdown("### NIRA Response")
                st.success(final_response)

                audio_path = synthesize_speech_to_file(
                    text=final_response,
                    language_code=tts_language,
                )

                with open(audio_path, "rb") as audio_file:
                    st.audio(audio_file.read(), format="audio/mp3")

            except Exception as exc:
                st.error(f"Voice demo failed: {exc}")

with tab_chat:
    left, right = st.columns([2, 1])

    with left:
        st.subheader("Transcript")

        if st.session_state.last_next_step and not conversation:
            with st.chat_message("assistant"):
                st.markdown(st.session_state.last_next_step)

        if not conversation:
            st.caption("No customer turns yet. Start by confirming identity.")

        for turn in conversation:
            role, content = normalize_turn(turn)
            with st.chat_message(role):
                st.markdown(content)

    with right:
        st.subheader("Latest NIRA response")
        final_response = nested(st.session_state.last_result, "final_response", default=None)
        if final_response:
            st.success(final_response)
        else:
            st.info("Send a customer message to see the generated response.")

        st.subheader("Latest actions")
        actions = nested(st.session_state.last_result, "actions", default=[])
        if actions:
            for action in actions:
                st.write(f"- {action}")
        else:
            st.caption("No actions yet.")

    user_text = st.chat_input("Type the customer's next message...")
    if user_text:
        try:
            process_turn(user_text)
            st.rerun()
        except RuntimeError as exc:
            st.session_state.last_error = str(exc)
            st.rerun()

with tab_trace:
    st.subheader("Latest reasoning snapshot")

    result = st.session_state.last_result
    if result:
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**Intent + entities**")
            st.json(result.get("intent_result", {}))

            st.markdown("**Agent decision**")
            st.json(result.get("agent_decision", {}))

        with col_b:
            st.markdown("**Risk result**")
            st.json(result.get("risk_result", {}))

            st.markdown("**Compliance + judge**")
            st.json(
                {
                    "compliance_result": result.get("compliance_result", {}),
                    "judge_result": result.get("judge_result", {}),
                }
            )
    else:
        st.info("No trace yet. Process one customer turn first.")

    st.divider()
    st.subheader("Full decision trace")

    try:
        refresh_trace()
    except RuntimeError as exc:
        st.warning(str(exc))

    trace_payload = st.session_state.last_trace or {}
    trace = trace_payload.get("decision_trace", [])

    if trace:
        trace_df = pd.DataFrame(trace)
        st.dataframe(trace_df, use_container_width=True, hide_index=True)

        with st.expander("Raw trace entries"):
            st.json(trace)
    else:
        st.caption("Decision trace is empty.")

with tab_summary:
    st.subheader("Post-call summary")

    summary = fetch_summary(st.session_state.api_base_url,
    st.session_state.active_session_id,)

    if not summary:
        st.info("No summary available yet. Complete at least one call turn and refresh.")
    else:
        st.markdown("### Summary")
        st.write(summary.get("summary_text", ""))

        st.markdown("### Key events")
        key_events = summary.get("key_events", [])
        if key_events:
            for event in key_events:
                st.write(f"- {event}")
        else:
            st.caption("No key events found.")

        st.markdown("### Next actions")
        next_actions = summary.get("next_actions", [])
        if next_actions:
            for action in next_actions:
                st.write(f"- {action}")
        else:
            st.caption("No next actions found.")

        st.markdown("### Raw summary JSON")
        st.json(summary)

with tab_customer:
    st.subheader("Customer profile")

    c1, c2, c3 = st.columns(3)
    c1.metric("Name", customer.get("name", "—"))
    c2.metric("Phone", customer.get("phone", "—"))
    c3.metric("Language", customer.get("preferred_language", session.get("language", "—")))

    st.subheader("Loan account")

    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Loan amount", format_money(loan.get("loan_amount")))
    l2.metric("Due date", loan.get("due_date", "—"))
    l3.metric("Overdue days", loan.get("overdue_days", "—"))
    l4.metric("Late fee", format_money(loan.get("late_fee")))

    st.subheader("Flags")
    flags = {
        "commitment_received": session.get("commitment_received"),
        "complaint_registered": session.get("complaint_registered"),
        "dispute_registered": session.get("dispute_registered"),
        "kyc_request_registered": session.get("kyc_request_registered"),
        "escalation_required": session.get("escalation_required"),
        "escalation_offered": session.get("escalation_offered"),
    }
    st.json(flags)

with tab_raw:
    st.subheader("Current session object")
    st.json(session)

    st.subheader("Latest turn result")
    st.json(st.session_state.last_result or {})
