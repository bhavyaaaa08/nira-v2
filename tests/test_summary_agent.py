from app.agents.summary_agent import SummaryAgent
from app.core.enums import RiskLevel
from app.core.schemas import CustomerProfile, LoanAccount
from app.core.state import CallState


def build_state() -> CallState:
    state = CallState()
    state.customer = CustomerProfile(
        name="Anita Verma",
        phone="9876543210",
        is_verified=True,
    )
    state.loan = LoanAccount(
        loan_amount=50000,
        due_date="2026-05-01",
        overdue_days=8,
        late_fee=500,
    )
    state.identity_verified = True
    state.risk_score = 30
    state.risk_level = RiskLevel.MEDIUM
    return state


def test_summary_agent_generates_basic_summary():
    state = build_state()
    state.outcome = "waiver_review_requested"
    state.escalation_required = True

    summary = SummaryAgent().summarize(state)

    assert summary.session_id == state.session_id
    assert summary.customer_name == "Anita Verma"
    assert summary.identity_verified is True
    assert summary.risk_level == RiskLevel.MEDIUM
    assert "waiver_review_requested" in summary.summary_text
    assert len(summary.key_events) > 0
    assert len(summary.next_actions) > 0


def test_summary_agent_includes_payment_commitment():
    state = build_state()
    state.mark_commitment(time_text="next week", amount=10000)

    summary = SummaryAgent().summarize(state)

    assert summary.customer_commitment == "₹10,000 by next week"
    assert "payment commitment" in " ".join(summary.key_events).lower()
    assert "Track promised payment date" in summary.next_actions[0]


def test_summary_agent_handles_unverified_customer():
    state = CallState()
    state.identity_verified = False

    summary = SummaryAgent().summarize(state)

    assert summary.identity_verified is False
    assert "not verified" in " ".join(summary.key_events).lower()
    assert "Verify customer identity" in summary.next_actions[0]