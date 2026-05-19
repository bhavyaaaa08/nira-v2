from app.agents.identity_agent import IdentityAgent
from app.core.enums import CallPhase, IdentityStatus
from app.core.schemas import CustomerProfile
from app.core.state import CallState


agent = IdentityAgent()


def test_identity_verified_with_full_name():
    result = agent.verify(
        user_text="Yes, I am Anita Verma speaking",
        expected_customer_name="Anita Verma",
    )

    assert result.status == IdentityStatus.VERIFIED
    assert result.verified is True
    assert result.confidence >= 0.90


def test_identity_verified_with_hinglish_confirmation():
    result = agent.verify(
        user_text="Haan main Anita bol rahi hoon",
        expected_customer_name="Anita Verma",
    )

    assert result.status == IdentityStatus.VERIFIED
    assert result.verified is True


def test_identity_verified_with_direct_yes():
    result = agent.verify(
        user_text="Yes",
        expected_customer_name="Anita Verma",
    )

    assert result.status == IdentityStatus.VERIFIED
    assert result.verified is True


def test_wrong_number_detected():
    result = agent.verify(
        user_text="Wrong number, I do not know Anita",
        expected_customer_name="Anita Verma",
    )

    assert result.status == IdentityStatus.WRONG_NUMBER
    assert result.verified is False
    assert "not discuss" in result.safe_reply.lower()


def test_uncertain_when_name_without_confirmation():
    result = agent.verify(
        user_text="Anita Verma",
        expected_customer_name="Anita Verma",
    )

    assert result.status == IdentityStatus.UNCERTAIN
    assert result.verified is False


def test_state_updates_after_verified_identity():
    state = CallState()
    state.customer = CustomerProfile(
        name="Anita Verma",
        phone="9876543210",
    )

    result = agent.verify(
        user_text="Haan main Anita bol rahi hoon",
        expected_customer_name="Anita Verma",
        state=state,
    )

    assert result.verified is True
    assert state.identity_verified is True
    assert state.phase == CallPhase.ACCOUNT_BRIEFING
    assert state.identity_attempts == 1