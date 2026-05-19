from app.agents.intent_entity_agent import IntentEntityAgent
from app.core.enums import Intent, Language


agent = IntentEntityAgent()


def test_promise_to_pay_hinglish():
    result = agent.analyze("Haan main kal shaam tak payment kar dungi")
    assert result.intent == Intent.PROMISE_TO_PAY
    assert result.entities.date == "tomorrow"
    assert result.entities.time == "evening"
    assert result.entities.language_hint == Language.HINGLISH


def test_payment_done_with_transaction_id():
    result = agent.analyze("I already paid yesterday, transaction id is TXN982341")
    assert result.intent == Intent.PAYMENT_DONE
    assert result.entities.date == "tomorrow" or result.entities.date is not None
    assert result.entities.transaction_id == "TXN982341"


def test_payment_method():
    result = agent.analyze("How do I pay through UPI?")
    assert result.intent == Intent.PAYMENT_METHOD
    assert result.entities.payment_method == "upi"


def test_waiver_request():
    result = agent.analyze("Can you remove the late fee?")
    assert result.intent == Intent.WAIVER_REQUEST


def test_complaint():
    result = agent.analyze("You people keep calling again and again, I want to complain")
    assert result.intent == Intent.COMPLAINT


def test_dispute():
    result = agent.analyze("This is wrong amount, I never took this loan")
    assert result.intent == Intent.DISPUTE


def test_kyc_update():
    result = agent.analyze("I want to update my mobile number for KYC")
    assert result.intent == Intent.KYC_UPDATE
    assert result.entities.kyc_field == "mobile_number"