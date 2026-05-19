from app.agents.orchestrator_agent import OrchestratorAgent
from app.core.enums import AgentName, CallPhase, Intent, PaymentStatus
from app.core.schemas import CustomerProfile, LoanAccount
from app.core.state import CallState


orchestrator = OrchestratorAgent()


def build_state(identity_verified: bool = False) -> CallState:
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
        overdue_days=8,
        status="active",
        late_fee=500,
    )
    state.identity_verified = identity_verified
    if identity_verified:
        state.phase = CallPhase.SERVICING
    return state


def test_orchestrator_requests_identity_before_account_details():
    state = build_state(identity_verified=False)

    result = orchestrator.process_turn(
        state=state,
        user_text="What is my due amount?",
    )

    assert result.agent_decision.selected_agent == AgentName.IDENTITY
    assert state.identity_verified is False
    assert "confirm" in result.final_response.lower()
    assert "₹50,000" not in result.final_response


def test_orchestrator_delivers_briefing_after_identity_verification():
    state = build_state(identity_verified=False)

    result = orchestrator.process_turn(
        state=state,
        user_text="Yes, I am Anita Verma speaking",
    )

    assert state.identity_verified is True
    assert result.agent_decision.selected_agent == AgentName.LOAN_SERVICING
    assert result.intent_result.intent == Intent.IDENTITY_CONFIRMATION
    assert "₹50,000" in result.final_response
    assert state.phase == CallPhase.SERVICING


def test_orchestrator_routes_promise_to_pay_to_loan_servicing():
    state = build_state(identity_verified=True)

    result = orchestrator.process_turn(
        state=state,
        user_text="I will pay tomorrow evening",
    )

    assert result.agent_decision.selected_agent == AgentName.LOAN_SERVICING
    assert result.intent_result.intent == Intent.PROMISE_TO_PAY
    assert state.commitment_received is True
    assert state.payment_status == PaymentStatus.PROMISED
    assert "noted" in result.final_response.lower()


def test_orchestrator_routes_payment_done_to_payment_operations():
    state = build_state(identity_verified=True)

    result = orchestrator.process_turn(
        state=state,
        user_text="I already paid, transaction id is OKPAY123",
    )

    assert result.agent_decision.selected_agent == AgentName.PAYMENT_OPERATIONS
    assert result.intent_result.intent == Intent.PAYMENT_DONE
    assert state.payment_status == PaymentStatus.VERIFIED
    assert result.final_response


def test_orchestrator_routes_complaint_to_complaint_agent():
    state = build_state(identity_verified=True)

    result = orchestrator.process_turn(
        state=state,
        user_text="Stop calling me again and again, I want to complain",
    )

    assert result.agent_decision.selected_agent == AgentName.COMPLAINT
    assert result.intent_result.intent == Intent.COMPLAINT
    assert state.complaint_registered is True
    assert "ticket" in result.final_response.lower()


def test_orchestrator_routes_fraud_to_fraud_dispute_agent():
    state = build_state(identity_verified=True)

    result = orchestrator.process_turn(
        state=state,
        user_text="This is fraud, I never took this loan",
    )

    assert result.agent_decision.selected_agent == AgentName.FRAUD_DISPUTE
    assert result.intent_result.intent == Intent.FRAUD_CLAIM
    assert state.dispute_registered is True
    assert state.escalation_required is True
    assert "fraud" in result.final_response.lower()


def test_orchestrator_routes_kyc_to_kyc_agent():
    state = build_state(identity_verified=True)

    result = orchestrator.process_turn(
        state=state,
        user_text="I want to update my mobile number for KYC",
    )

    assert result.agent_decision.selected_agent == AgentName.KYC
    assert result.intent_result.intent == Intent.KYC_UPDATE
    assert state.kyc_request_registered is True
    assert "ticket" in result.final_response.lower()


def test_orchestrator_routes_human_escalation():
    state = build_state(identity_verified=True)

    result = orchestrator.process_turn(
        state=state,
        user_text="Connect me to a human agent",
    )

    assert result.agent_decision.selected_agent == AgentName.ORCHESTRATOR
    assert result.intent_result.intent == Intent.ESCALATION_REQUEST
    assert state.escalation_required is True
    assert state.phase == CallPhase.ESCALATION


def test_orchestrator_creates_decision_trace():
    state = build_state(identity_verified=True)

    result = orchestrator.process_turn(
        state=state,
        user_text="I cannot pay right now",
    )

    assert len(state.decision_trace) == 1

    trace = state.decision_trace[0]

    assert trace["detected_intent"] == Intent.CANNOT_PAY.value
    assert trace["selected_agent"] == AgentName.LOAN_SERVICING.value
    assert trace["final_response"] == result.final_response
    assert "risk_score" in trace
    assert "compliance_status" in trace
    assert "judge_score" in trace


def test_orchestrator_logs_user_and_assistant_turns():
    state = build_state(identity_verified=True)

    orchestrator.process_turn(
        state=state,
        user_text="How do I pay through UPI?",
    )

    assert len(state.conversation) == 2
    assert state.conversation[0].role == "user"
    assert state.conversation[1].role == "assistant"