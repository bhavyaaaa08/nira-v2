from app.agents.intent_entity_agent import IntentEntityAgent
from app.agents.orchestrator_agent import OrchestratorAgent
from app.core.enums import Intent, Language
from app.core.state import CallState
from app.core.schemas import CustomerProfile, LoanAccount


def build_state(preferred_language: Language = Language.ENGLISH) -> CallState:
    state = CallState(language=preferred_language)

    state.customer = CustomerProfile(
        name="Anita Verma",
        phone="9876543210",
        preferred_language=preferred_language,
        is_verified=False,
    )

    state.loan = LoanAccount(
        loan_amount=50000,
        due_date="2026-05-01",
        overdue_days=8,
        status="active",
        late_fee=500,
    )

    return state


def test_hinglish_identity_verification():
    state = build_state()
    orchestrator = OrchestratorAgent()

    result = orchestrator.process_turn(
        state=state,
        user_text="han me anita bol rahi hu",
    )

    assert state.identity_verified is True
    assert result.intent_result.intent == Intent.IDENTITY_CONFIRMATION
    assert result.final_response


def test_salary_delayed_uses_llm_or_rule_as_cannot_pay():
    state = build_state()
    orchestrator = OrchestratorAgent()

    orchestrator.process_turn(state, "han me anita bol rahi hu")
    result = orchestrator.process_turn(state, "pata nahi salary kab aayegi")

    assert result.intent_result.intent == Intent.CANNOT_PAY
    assert "extension" in result.final_response.lower() or "review" in result.final_response.lower()


def test_late_fee_hinglish_intent():
    agent = IntentEntityAgent()

    result = agent.analyze("late fee kyun laga hai")

    assert result.intent == Intent.PENALTY_QUESTION
    assert result.entities.language_hint == Language.HINGLISH


def test_payment_method_hinglish_intent():
    agent = IntentEntityAgent()

    result = agent.analyze("payment kaise karu")

    assert result.intent == Intent.PAYMENT_METHOD
    assert result.entities.language_hint == Language.HINGLISH


def test_extension_hinglish_intent():
    agent = IntentEntityAgent()

    result = agent.analyze("mujhe thoda time chahiye")

    assert result.intent == Intent.NEEDS_EXTENSION
    assert result.entities.language_hint == Language.HINGLISH


def test_complaint_hinglish_intent():
    agent = IntentEntityAgent()

    result = agent.analyze("baar baar call mat karo")

    assert result.intent == Intent.COMPLAINT
    assert result.entities.language_hint == Language.HINGLISH


def test_fraud_or_dispute_hinglish_intent():
    agent = IntentEntityAgent()

    result = agent.analyze("ye loan mera nahi hai")

    assert result.intent in {Intent.FRAUD_CLAIM, Intent.DISPUTE}
    assert result.entities.language_hint == Language.HINGLISH


def test_payment_done_with_transaction_id():
    agent = IntentEntityAgent()

    result = agent.analyze("maine payment kar diya UTR OKPAY123")

    assert result.intent == Intent.PAYMENT_DONE
    assert result.entities.transaction_id == "OKPAY123"
    assert result.entities.language_hint == Language.HINGLISH


def test_localization_trace_exists_after_hinglish_turn():
    state = build_state()
    orchestrator = OrchestratorAgent()

    orchestrator.process_turn(state, "han me anita bol rahi hu")

    latest_trace = state.decision_trace[-1]

    assert "localization_trace" in latest_trace
    assert latest_trace["localization_trace"]["target_language"] in {
        "hinglish",
        "hi",
        "en",
        "unknown",
    }


def test_localization_trace_has_final_response():
    state = build_state()
    orchestrator = OrchestratorAgent()

    result = orchestrator.process_turn(state, "han me anita bol rahi hu")

    latest_trace = state.decision_trace[-1]
    localization_trace = latest_trace["localization_trace"]

    assert localization_trace["original_response"]
    assert localization_trace["final_response"]
    assert result.final_response == localization_trace["final_response"]


def test_full_hinglish_pipeline_complaint():
    state = build_state()
    orchestrator = OrchestratorAgent()

    orchestrator.process_turn(state, "han me anita bol rahi hu")
    result = orchestrator.process_turn(state, "baar baar call mat karo")

    assert result.intent_result.intent == Intent.COMPLAINT
    assert state.complaint_registered is True
    assert result.final_response
    assert "localization_trace" in state.decision_trace[-1]