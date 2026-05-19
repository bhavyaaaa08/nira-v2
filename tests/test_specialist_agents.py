from app.agents.complaint_agent import ComplaintAgent
from app.agents.fraud_dispute_agent import FraudDisputeAgent
from app.agents.intent_entity_agent import IntentEntityAgent
from app.agents.kyc_agent import KYCAgent
from app.core.enums import CallPhase, RiskLevel, TicketCategory
from app.core.schemas import CustomerProfile, LoanAccount
from app.core.state import CallState


intent_agent = IntentEntityAgent()
complaint_agent = ComplaintAgent()
fraud_dispute_agent = FraudDisputeAgent()
kyc_agent = KYCAgent()


def build_state() -> CallState:
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
        overdue_days=12,
        status="active",
        late_fee=500,
    )
    state.identity_verified = True
    return state


def test_complaint_agent_registers_complaint_ticket():
    state = build_state()
    intent_result = intent_agent.analyze(
        "Stop calling me again and again, I want to complain"
    )

    response = complaint_agent.respond(state, intent_result)
    ticket = response.metadata["ticket"]

    assert response.outcome == "complaint_registered"
    assert state.complaint_registered is True
    assert state.phase == CallPhase.COMPLAINT
    assert ticket["category"] == TicketCategory.COMPLAINT
    assert ticket["ticket_id"].startswith("COMP-")


def test_complaint_ticket_has_medium_priority_by_default():
    state = build_state()
    intent_result = intent_agent.analyze("I want to complain about repeated calls")

    response = complaint_agent.respond(state, intent_result)
    ticket = response.metadata["ticket"]

    assert ticket["priority"] == RiskLevel.MEDIUM


def test_dispute_agent_registers_dispute_ticket():
    state = build_state()
    intent_result = intent_agent.analyze("This is wrong amount, I never took this loan")

    response = fraud_dispute_agent.respond(state, intent_result)
    ticket = response.metadata["ticket"]

    assert response.outcome == "dispute_registered"
    assert state.dispute_registered is True
    assert state.phase == CallPhase.DISPUTE
    assert ticket["category"] == TicketCategory.DISPUTE
    assert ticket["ticket_id"].startswith("DISP-")


def test_fraud_claim_creates_critical_fraud_ticket():
    state = build_state()
    intent_result = intent_agent.analyze("This is fraud, I never took this loan")

    response = fraud_dispute_agent.respond(state, intent_result)
    ticket = response.metadata["ticket"]

    assert response.outcome == "fraud_review_registered"
    assert state.dispute_registered is True
    assert state.escalation_required is True
    assert state.phase == CallPhase.ESCALATION
    assert ticket["category"] == TicketCategory.FRAUD
    assert ticket["priority"] == RiskLevel.CRITICAL
    assert ticket["ticket_id"].startswith("FRAUD-")


def test_kyc_agent_registers_mobile_update_ticket():
    state = build_state()
    intent_result = intent_agent.analyze("I want to update my mobile number for KYC")

    response = kyc_agent.respond(state, intent_result)
    ticket = response.metadata["ticket"]

    assert response.outcome == "kyc_update_requested"
    assert state.kyc_request_registered is True
    assert state.phase == CallPhase.KYC
    assert response.metadata["kyc_field"] == "mobile_number"
    assert ticket["category"] == TicketCategory.KYC
    assert ticket["ticket_id"].startswith("KYC-")


def test_kyc_agent_registers_address_update_ticket():
    state = build_state()
    intent_result = intent_agent.analyze("My address changed, please update KYC")

    response = kyc_agent.respond(state, intent_result)

    assert response.outcome == "kyc_update_requested"
    assert response.metadata["kyc_field"] == "address"
    assert "address" in response.response_text.lower()


def test_dispute_agent_does_not_argue_with_customer():
    state = build_state()
    intent_result = intent_agent.analyze("This loan is not mine")

    response = fraud_dispute_agent.respond(state, intent_result)

    assert "investigate" in response.response_text.lower() or "review" in response.response_text.lower()
    assert "you are wrong" not in response.response_text.lower()


def test_complaint_response_apologizes():
    state = build_state()
    intent_result = intent_agent.analyze("Your service is rude and bad")

    response = complaint_agent.respond(state, intent_result)

    assert "sorry" in response.response_text.lower()


def test_kyc_response_requires_security_verification():
    state = build_state()
    intent_result = intent_agent.analyze("Update my PAN for KYC")

    response = kyc_agent.respond(state, intent_result)

    assert "security" in response.response_text.lower()
    assert "verify" in response.response_text.lower()