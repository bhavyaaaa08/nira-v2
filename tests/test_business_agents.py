from app.agents.intent_entity_agent import IntentEntityAgent
from app.agents.loan_servicing_agent import LoanServicingAgent
from app.agents.payment_operations_agent import PaymentOperationsAgent
from app.core.enums import CallPhase, PaymentStatus
from app.core.schemas import CustomerProfile, LoanAccount
from app.core.state import CallState


intent_agent = IntentEntityAgent()
loan_agent = LoanServicingAgent()
payment_agent = PaymentOperationsAgent()


def build_state(overdue_days: int = 5, amount: float = 50000) -> CallState:
    state = CallState()
    state.customer = CustomerProfile(
        customer_id=1,
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
    state.identity_verified = True
    return state


def test_initial_briefing_for_overdue_loan():
    state = build_state(overdue_days=5, amount=50000)

    response = loan_agent.initial_briefing(state)

    assert response.next_phase == CallPhase.SERVICING
    assert "₹50,000" in response.response_text
    assert "5 days overdue" in response.response_text
    assert state.phase == CallPhase.SERVICING


def test_promise_to_pay_response_updates_state():
    state = build_state()
    intent_result = intent_agent.analyze("I will pay tomorrow evening")

    response = loan_agent.respond(state, intent_result)

    assert response.outcome == "promise_to_pay"
    assert state.commitment_received is True
    assert state.payment_status == PaymentStatus.PROMISED
    assert "tomorrow" in response.response_text.lower()


def test_cannot_pay_offers_extension_review():
    state = build_state()
    intent_result = intent_agent.analyze("I cannot pay right now")

    response = loan_agent.respond(state, intent_result)

    assert response.outcome == "extension_review_offered"
    assert "executive" in response.response_text.lower()
    assert "review" in response.response_text.lower()
    assert "would you like me to raise" in response.response_text.lower()
    assert "offer_extension_review" in response.actions


def test_late_fee_question():
    state = build_state()
    intent_result = intent_agent.analyze("Why is there a late fee?")

    response = loan_agent.respond(state, intent_result)

    assert "₹500" in response.response_text
    assert "due date" in response.response_text.lower()


def test_payment_done_without_transaction_id_requests_reference():
    state = build_state()
    intent_result = intent_agent.analyze("I already paid yesterday")

    response = payment_agent.respond(state, intent_result)

    assert response.outcome == "payment_verification_pending"
    assert "transaction reference" in response.response_text.lower()
    assert state.payment_status == PaymentStatus.VERIFICATION_PENDING


def test_payment_done_with_verified_transaction_id():
    state = build_state()
    intent_result = intent_agent.analyze("I already paid, transaction id is OKPAY123")

    response = payment_agent.respond(state, intent_result)

    assert response.outcome == "payment_verified"
    assert state.payment_status == PaymentStatus.VERIFIED
    assert response.next_phase == CallPhase.CLOSING


def test_payment_amount_mismatch():
    state = build_state(amount=50000)
    intent_result = intent_agent.analyze("I paid Rs 10000, transaction id is OKPAY123")

    response = payment_agent.respond(state, intent_result)

    assert response.outcome == "payment_amount_mismatch"
    assert state.payment_status == PaymentStatus.AMOUNT_MISMATCH
    assert response.next_phase == CallPhase.ESCALATION


def test_transaction_not_found():
    state = build_state()
    intent_result = intent_agent.analyze("I paid, transaction id is MISS987654")

    response = payment_agent.respond(state, intent_result)

    assert response.outcome == "transaction_not_found"
    assert state.payment_status == PaymentStatus.TRANSACTION_NOT_FOUND