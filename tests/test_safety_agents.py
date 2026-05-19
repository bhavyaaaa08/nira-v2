from app.agents.compliance_agent import ComplianceAgent
from app.agents.response_judge_agent import ResponseJudgeAgent
from app.core.enums import CallPhase, ComplianceStatus, PaymentStatus
from app.core.schemas import AgentResponse, CustomerProfile, LoanAccount
from app.core.state import CallState


compliance_agent = ComplianceAgent()
judge_agent = ResponseJudgeAgent()


def build_state(identity_verified: bool = True) -> CallState:
    state = CallState()
    state.customer = CustomerProfile(
        customer_id=1,
        name="Anita Verma",
        phone="9876543210",
    )
    state.loan = LoanAccount(
        loan_id=1,
        customer_id=1,
        loan_amount=50000,
        due_date="2026-05-01",
        overdue_days=10,
        status="active",
        late_fee=500,
    )
    state.identity_verified = identity_verified
    return state


def test_compliance_blocks_account_details_before_identity_verification():
    state = build_state(identity_verified=False)

    result = compliance_agent.check(
        response_text="Your loan payment of ₹50,000 is overdue by 10 days.",
        state=state,
    )

    assert result.status == ComplianceStatus.BLOCKED
    assert "account_details_before_identity_verification" in result.violations
    assert "confirm" in result.safe_response.lower()


def test_compliance_passes_account_details_after_identity_verification():
    state = build_state(identity_verified=True)

    result = compliance_agent.check(
        response_text="Your loan payment of ₹50,000 is overdue by 10 days.",
        state=state,
    )

    assert result.status == ComplianceStatus.PASSED
    assert result.violations == []


def test_compliance_rewrites_coercive_language():
    state = build_state(identity_verified=True)

    result = compliance_agent.check(
        response_text="This is your last warning. Legal action will be taken.",
        state=state,
    )

    assert result.status == ComplianceStatus.NEEDS_REWRITE
    assert "coercive_or_threatening_language" in result.violations
    assert "payment options" in result.safe_response.lower()


def test_compliance_blocks_false_payment_confirmation():
    state = build_state(identity_verified=True)
    state.payment_status = PaymentStatus.VERIFICATION_PENDING

    result = compliance_agent.check(
        response_text="Your payment is confirmed and your account is closed.",
        state=state,
    )

    assert result.status == ComplianceStatus.NEEDS_REWRITE
    assert "unverified_payment_or_account_closure_claim" in result.violations
    assert "verification" in result.safe_response.lower()


def test_compliance_allows_payment_confirmation_when_verified():
    state = build_state(identity_verified=True)
    state.payment_status = PaymentStatus.VERIFIED

    result = compliance_agent.check(
        response_text="Your payment is confirmed.",
        state=state,
    )

    assert result.status == ComplianceStatus.PASSED


def test_enforce_replaces_unsafe_response():
    state = build_state(identity_verified=False)

    response = AgentResponse(
        agent_name="loan_servicing_agent",
        response_text="Your loan amount is ₹50,000 and it is overdue.",
        next_phase=CallPhase.SERVICING,
    )

    safe_response = compliance_agent.enforce(response, state)

    assert "confirm" in safe_response.response_text.lower()
    assert "compliance_rewrite_applied" in safe_response.actions


def test_response_judge_shortens_long_response():
    state = build_state(identity_verified=True)

    long_response = (
        "I understand your concern. I can help you with the payment process. "
        "You can pay using UPI, bank transfer, the loan app, or the payment portal. "
        "After that, please share the transaction reference number. "
        "Then I can mark it for verification. "
        "This may take some time to reflect."
    )

    result = judge_agent.judge(long_response, state)

    assert "too_long_for_voice" in result.issues
    assert len(result.final_response.split()) <= 55


def test_response_judge_detects_repetition():
    state = build_state(identity_verified=True)
    state.last_agent_response = "You can pay through UPI or the loan app."

    result = judge_agent.judge(
        response_text="You can pay through UPI or the loan app.",
        state=state,
    )

    assert "repeats_previous_response" in result.issues


def test_response_judge_uses_compliance_safe_response():
    state = build_state(identity_verified=False)

    compliance_result = compliance_agent.check(
        response_text="Your loan payment of ₹50,000 is overdue.",
        state=state,
    )

    result = judge_agent.judge(
        response_text="Your loan payment of ₹50,000 is overdue.",
        state=state,
        compliance_result=compliance_result,
    )

    assert result.approved is True
    assert "confirm" in result.final_response.lower()
    assert "compliance_rewrite_required" in result.issues


def test_finalize_attaches_judge_result():
    state = build_state(identity_verified=True)

    response = AgentResponse(
        agent_name="loan_servicing_agent",
        response_text="You can pay through UPI. Please keep the transaction reference.",
        next_phase=CallPhase.PAYMENT,
    )

    final_response = judge_agent.finalize(response, state)

    assert "judge_result" in final_response.metadata
    assert final_response.response_text