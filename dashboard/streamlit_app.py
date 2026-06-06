from __future__ import annotations

from datetime import datetime
from streamlit_mic_recorder import mic_recorder

import os
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd
import requests
import streamlit as st

from app.services.stt_service import detect_audio_encoding, transcribe_audio_bytes
from app.services.tts_service import synthesize_speech_to_file
from data.seed_data import get_demo_profiles

DEFAULT_API_BASE_URL = os.getenv("NIRA_API_BASE_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT = 15


st.set_page_config(
    page_title="NIRA v2 Dashboard",
    page_icon="🎙️",
    layout="wide",
)


def init_state() -> None:
    defaults = {
        "api_base_url": DEFAULT_API_BASE_URL,
        "active_session_id": None,
        "active_session": None,
        "last_result": None,
        "last_trace": None,
        "last_next_step": None,
        "last_error": None,
        "last_voice_transcript": None,
        "last_voice_response": None,
        "last_voice_audio_path": None,
        "voice_history": [],
    }

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

def profile_label(profile: dict[str, Any]) -> str:
    customer = profile.get("customer") or {}
    loan = profile.get("loan") or {}

    return (
        f"{customer.get('customer_id')} • "
        f"{customer.get('name')} • "
        f"{customer.get('phone')} • "
        f"{loan.get('status', 'no-loan')}"
    )

init_state()


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
    st.session_state.last_voice_transcript = None
    st.session_state.last_voice_response = None
    st.session_state.last_voice_audio_path = None
    st.session_state.voice_history = []


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
    st.session_state.last_voice_transcript = None
    st.session_state.last_voice_response = None
    st.session_state.last_voice_audio_path = None
    st.session_state.voice_history = []


def get_preferred_language() -> str:
    session = st.session_state.active_session or {}
    customer = session.get("customer") or {}

    return (
        customer.get("preferred_language")
        or session.get("language")
        or "hi"
    )


def get_stt_language_for_session() -> str:
    language = get_preferred_language()

    mapping = {
        "en": "en-IN",
        "hi": "hi-IN",
        "hinglish": "hi-IN",
        "ta": "ta-IN",
    }

    return mapping.get(language, "hi-IN")


def get_stt_alternatives_for_session() -> list[str]:
    language = get_preferred_language()

    mapping = {
        "en": ["hi-IN"],
        "hi": ["en-IN"],
        "hinglish": ["en-IN"],
        "ta": ["en-IN"],
    }

    return mapping.get(language, ["en-IN"])


def get_tts_language_for_session() -> str:
    language = get_preferred_language()

    mapping = {
        "en": "en-IN",
        "hi": "hi-IN",
        "hinglish": "hi-IN",
        "ta": "ta-IN",
    }

    return mapping.get(language, "hi-IN")


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

    profiles = get_demo_profiles()

    selected_profile = st.selectbox(
        "Demo customer profile",
        options=profiles,
        format_func=profile_label,
    )

    selected_customer = selected_profile.get("customer") or {}
    selected_loan = selected_profile.get("loan") or {}

    customer_name = st.text_input(
        "Customer name",
        value=selected_customer.get("name", "Anita Verma"),
    )

    phone = st.text_input(
        "Phone",
        value=selected_customer.get("phone", "9876543210"),
    )

    loan_amount = st.number_input(
        "Loan amount",
        min_value=0.0,
        value=float(selected_loan.get("loan_amount", 50000) or 50000),
        step=1000.0,
    )

    due_date = st.text_input(
        "Due date",
        value=selected_loan.get("due_date", "2026-05-01"),
    )

    overdue_days = st.number_input(
        "Overdue days",
        min_value=0,
        value=int(selected_loan.get("overdue_days", 8) or 8),
        step=1,
    )

    late_fee = st.number_input(
        "Late fee",
        min_value=0.0,
        value=float(selected_loan.get("late_fee", 500) or 500),
        step=100.0,
    )

    language_options = ["en", "hi", "hinglish", "ta"]
    selected_language = selected_customer.get("preferred_language", "en")

    preferred_language = st.selectbox(
        "Preferred language",
        options=language_options,
        index=language_options.index(selected_language)
        if selected_language in language_options
        else 0,
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

tab_chat, tab_voice, tab_trace, tab_analytics, tab_summary, tab_customer, tab_raw = st.tabs(
    [
        "Conversation",
        "Voice Demo",
        "Decision trace",
        "Analytics",
        "Summary",
        "Customer + loan",
        "Raw JSON",
    ]
)


with tab_voice:
    st.subheader("Voice Demo")
    st.caption("Upload customer audio or enter a transcript, then generate NIRA's voice response.")

    st.markdown("### Record from microphone")

    mic_audio = mic_recorder(
        start_prompt="Start recording",
        stop_prompt="Stop recording",
        just_once=False,
        use_container_width=True,
        key="voice_mic_recorder",
    )

    uploaded_audio = st.file_uploader(
        "Upload customer audio",
        type=["wav", "mp3", "webm"],
    )

    manual_text = st.text_area(
        "Manual transcript fallback",
        placeholder="Example: meri salary nahi aai hai",
        height=100,
    )

    if st.button("Process voice turn", type="primary"):
        try:
            transcript = manual_text.strip()
            input_mode = "manual"

            if mic_audio and not transcript:
                audio_bytes = mic_audio["bytes"]
                encoding = detect_audio_encoding("recording.wav")
                input_mode = "microphone"

                transcript = transcribe_audio_bytes(
                    audio_bytes=audio_bytes,
                    language_code=get_stt_language_for_session(),
                    alternative_language_codes=get_stt_alternatives_for_session(),
                    encoding=encoding,
                )

            elif uploaded_audio is not None and not transcript:
                audio_bytes = uploaded_audio.getvalue()
                encoding = detect_audio_encoding(uploaded_audio.name)
                input_mode = "audio"

                transcript = transcribe_audio_bytes(
                    audio_bytes=audio_bytes,
                    language_code=get_stt_language_for_session(),
                    alternative_language_codes=get_stt_alternatives_for_session(),
                    encoding=encoding,
                )

            if not transcript:
                st.error("Please upload audio or enter a manual transcript.")
                st.stop()

            process_turn(transcript)

            final_response = nested(
                st.session_state.last_result,
                "final_response",
                default="",
            )

            if not final_response:
                st.warning("No NIRA response received.")
                st.stop()

            audio_path = synthesize_speech_to_file(
                text=final_response,
                language_code=get_tts_language_for_session(),
            )

            st.session_state.last_voice_transcript = transcript
            st.session_state.last_voice_response = final_response
            st.session_state.last_voice_audio_path = audio_path

            st.session_state.voice_history.append(
                {
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "input_mode": input_mode,
                    "transcript": transcript,
                    "response": final_response,
                    "audio_path": audio_path,
                }
            )

            st.rerun()

        except Exception as exc:
            st.error(f"Voice demo failed: {exc}")

    if st.session_state.last_voice_transcript:
        st.markdown("### Transcript")
        st.info(st.session_state.last_voice_transcript)

    if st.session_state.last_voice_response:
        st.markdown("### NIRA Response")
        st.success(st.session_state.last_voice_response)

    audio_path = st.session_state.last_voice_audio_path
    if audio_path and os.path.exists(audio_path):
        st.markdown("### Audio Reply")
        with open(audio_path, "rb") as audio_file:
            st.audio(audio_file.read(), format="audio/mp3")


        if st.session_state.voice_history:
            st.markdown("### Voice Interaction History")

            for index, item in enumerate(reversed(st.session_state.voice_history), start=1):
                with st.expander(f"Voice turn {index} • {item['timestamp']} • {item['input_mode']}"):
                    st.markdown("**Transcript**")
                    st.write(item["transcript"])

                    st.markdown("**NIRA Response**")
                    st.write(item["response"])

                    history_audio_path = item.get("audio_path")
                    if history_audio_path and os.path.exists(history_audio_path):
                        st.audio(history_audio_path)


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

with tab_analytics:
    st.subheader("Call Analytics")
    st.caption("Session-level operational analytics generated from NIRA decision traces and call state.")

    trace_payload = st.session_state.last_trace or {}
    trace = trace_payload.get("decision_trace", []) or session.get("decision_trace", [])

    if not trace:
        st.info("No analytics yet. Complete at least one customer turn first.")
    else:
        trace_df = pd.DataFrame(trace)

        total_turns = len(trace_df)
        escalation_count = int(session.get("escalation_required") is True)
        complaint_count = int(session.get("complaint_registered") is True)
        dispute_count = int(session.get("dispute_registered") is True)
        kyc_count = int(session.get("kyc_request_registered") is True)

        llm_fallback_used_count = 0
        llm_fallback_attempted_count = 0

        if "llm_trace" in trace_df.columns:
            for item in trace_df["llm_trace"].dropna():
                if isinstance(item, dict):
                    if item.get("llm_fallback_used"):
                        llm_fallback_used_count += 1
                    if item.get("llm_fallback_attempted"):
                        llm_fallback_attempted_count += 1

        avg_judge_score = None
        if "judge_score" in trace_df.columns:
            avg_judge_score = pd.to_numeric(
                trace_df["judge_score"],
                errors="coerce",
            ).mean()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total turns", total_turns)
        c2.metric("Current risk", f"{session.get('risk_level', '—')} / {session.get('risk_score', 0)}")
        c3.metric("Avg judge score", f"{avg_judge_score:.1f}" if pd.notna(avg_judge_score) else "—")
        c4.metric("LLM fallback used", llm_fallback_used_count)

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Complaints", complaint_count)
        c6.metric("Disputes", dispute_count)
        c7.metric("KYC requests", kyc_count)
        c8.metric("Escalations", escalation_count)

        st.divider()

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("### Intent Distribution")
            if "detected_intent" in trace_df.columns:
                intent_counts = trace_df["detected_intent"].value_counts().reset_index()
                intent_counts.columns = ["intent", "count"]
                st.bar_chart(intent_counts, x="intent", y="count")
                st.dataframe(intent_counts, use_container_width=True, hide_index=True)
            else:
                st.caption("No intent data found.")

        with col_right:
            st.markdown("### Agent Usage")
            if "selected_agent" in trace_df.columns:
                agent_counts = trace_df["selected_agent"].value_counts().reset_index()
                agent_counts.columns = ["agent", "count"]
                st.bar_chart(agent_counts, x="agent", y="count")
                st.dataframe(agent_counts, use_container_width=True, hide_index=True)
            else:
                st.caption("No agent data found.")

        st.divider()

        trend_left, trend_right = st.columns(2)

        with trend_left:
            st.markdown("### Risk Trend")
            if {"turn_number", "risk_score"}.issubset(trace_df.columns):
                risk_trend = trace_df[["turn_number", "risk_score"]].copy()
                risk_trend["risk_score"] = pd.to_numeric(
                    risk_trend["risk_score"],
                    errors="coerce",
                )
                st.line_chart(risk_trend, x="turn_number", y="risk_score")
                st.dataframe(risk_trend, use_container_width=True, hide_index=True)
            else:
                st.caption("No risk trend data found.")

        with trend_right:
            st.markdown("### Judge Score Trend")
            if {"turn_number", "judge_score"}.issubset(trace_df.columns):
                judge_trend = trace_df[["turn_number", "judge_score"]].copy()
                judge_trend["judge_score"] = pd.to_numeric(
                    judge_trend["judge_score"],
                    errors="coerce",
                )
                st.line_chart(judge_trend, x="turn_number", y="judge_score")
                st.dataframe(judge_trend, use_container_width=True, hide_index=True)
            else:
                st.caption("No judge score trend data found.")

        st.divider()

        st.markdown("### Compliance Overview")

        if "compliance_status" in trace_df.columns:
            compliance_counts = trace_df["compliance_status"].value_counts().reset_index()
            compliance_counts.columns = ["status", "count"]
            st.bar_chart(compliance_counts, x="status", y="count")
            st.dataframe(compliance_counts, use_container_width=True, hide_index=True)
        else:
            st.caption("No compliance status data found.")

        if "compliance_violations" in trace_df.columns:
            violations = []

            for item in trace_df["compliance_violations"].dropna():
                if isinstance(item, list):
                    violations.extend(item)

            if violations:
                violation_df = pd.Series(violations).value_counts().reset_index()
                violation_df.columns = ["violation", "count"]

                st.markdown("### Compliance Violations")
                st.dataframe(violation_df, use_container_width=True, hide_index=True)
            else:
                st.caption("No compliance violations in this session.")

        st.divider()

        st.markdown("### LLM Fallback Overview")

        llm_cols = st.columns(3)
        llm_cols[0].metric("Fallback attempted", llm_fallback_attempted_count)
        llm_cols[1].metric("Fallback used", llm_fallback_used_count)

        fallback_rate = (
            (llm_fallback_used_count / total_turns) * 100
            if total_turns > 0
            else 0
        )
        llm_cols[2].metric("Fallback usage rate", f"{fallback_rate:.0f}%")

        with st.expander("Raw analytics dataframe"):
            st.dataframe(trace_df, use_container_width=True, hide_index=True)


with tab_summary:
    st.subheader("Post-call summary")

    summary = fetch_summary(
        st.session_state.api_base_url,
        st.session_state.active_session_id,
    )

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