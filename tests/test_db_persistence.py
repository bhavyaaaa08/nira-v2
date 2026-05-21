from app.db.database import init_db
from app.services.session_store import SessionStore


def test_session_store_persists_and_reloads_session():
    init_db()

    store = SessionStore()

    state = store.create_session(
        customer_name="Anita Verma",
        phone="9999999999",
        loan_amount=50000,
        due_date="2026-05-01",
        overdue_days=8,
        late_fee=500,
    )

    session_id = state.session_id

    state.add_turn("user", "yes its anita")
    state.add_turn("assistant", "Thank you for confirming.")
    state.outcome = "test_outcome"

    store.save_session(state)
    store.clear_memory_cache()

    reloaded = store.get_session(session_id)

    assert reloaded is not None
    assert reloaded.session_id == session_id
    assert reloaded.customer is not None
    assert reloaded.customer.name == "Anita Verma"
    assert reloaded.loan is not None
    assert reloaded.loan.loan_amount == 50000
    assert reloaded.outcome == "test_outcome"
    assert len(reloaded.conversation) == 2