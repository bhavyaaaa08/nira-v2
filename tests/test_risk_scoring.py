from app.agents.intent_entity_agent import IntentEntityAgent
from app.agents.risk_scoring_agent import RiskScoringAgent
from app.core.enums import Intent, RiskLevel
from app.core.schemas import CustomerProfile, LoanAccount
from app.core.state import CallState


intent_agent = IntentEntityAgent()
risk_agent = RiskScoringAgent()


def build_state(overdue_days: int = 0, amount: float = 10000) -> CallState:
    state = CallState()
    state.customer = CustomerProfile(
        name="Anita Verma",
        phone="9876543210",
    )
    state.loan = LoanAccount(
        loan_id=1,
        customer_id=1,
        loan_amount=amount,
        due_date="2026-05-01",
        overdue_days=overdue_days,
        status="active",
        late_fee=500,
    )
    return state


def test_low_risk_for_normal_payment_method_query():
    state = build_state(overdue_days=0, amount=8000)
    intent_result = intent_agent.analyze("How do I pay through UPI?")

    result = risk_agent.analyze(
        state=state,
        intent_result=intent_result,
        user_text="How do I pay through UPI?",
    )

    assert result.level == RiskLevel.LOW
    assert result.score < 30
    assert state.risk_score == result.score


def test_medium_risk_for_overdue_loan():
    state = build_state(overdue_days=10, amount=50000)
    intent_result = intent_agent.analyze("I will pay tomorrow")

    result = risk_agent.analyze(
        state=state,
        intent_result=intent_result,
        user_text="I will pay tomorrow",
    )

    assert result.level in {RiskLevel.MEDIUM, RiskLevel.LOW}
    assert result.score >= 15


def test_high_risk_for_fraud_claim():
    state = build_state(overdue_days=20, amount=70000)
    intent_result = intent_agent.analyze("This is fraud, I never took this loan")

    result = risk_agent.analyze(
        state=state,
        intent_result=intent_result,
        user_text="This is fraud, I never took this loan",
    )

    assert result.level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    assert result.score >= 60
    assert "fraud" in result.recommended_action.lower()


def test_high_risk_for_complaint_and_frustration():
    state = build_state(overdue_days=15, amount=50000)
    intent_result = intent_agent.analyze(
        "Stop calling me again and again, this is harassment"
    )

    result = risk_agent.analyze(
        state=state,
        intent_result=intent_result,
        user_text="Stop calling me again and again, this is harassment",
    )

    assert result.level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    assert result.score >= 60
    assert any("frustrated" in reason.lower() for reason in result.reasons)


def test_commitment_reduces_risk():
    state = build_state(overdue_days=10, amount=50000)
    state.mark_commitment(time_text="tomorrow evening")

    intent_result = intent_agent.analyze("I will pay tomorrow evening")

    result = risk_agent.analyze(
        state=state,
        intent_result=intent_result,
        user_text="I will pay tomorrow evening",
    )

    assert result.score < 40
    assert result.recommended_action == "Record promise-to-pay and schedule follow-up reminder."


def test_state_updates_after_risk_analysis():
    state = build_state(overdue_days=35, amount=120000)
    intent_result = intent_agent.analyze("I cannot pay right now")

    result = risk_agent.analyze(
        state=state,
        intent_result=intent_result,
        user_text="I cannot pay right now",
    )

    assert state.risk_score == result.score
    assert state.risk_level == result.level
    assert state.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}