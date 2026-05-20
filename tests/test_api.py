from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_demo_session() -> str:
    response = client.post(
        "/api/calls/sessions",
        json={
            "customer_name": "Anita Verma",
            "phone": "9876543210",
            "loan_amount": 50000,
            "due_date": "2026-05-01",
            "overdue_days": 8,
            "late_fee": 500,
            "preferred_language": "en",
        },
    )

    assert response.status_code == 200

    data = response.json()
    return data["session"]["session_id"]


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_call_session():
    response = client.post(
        "/api/calls/sessions",
        json={
            "customer_name": "Anita Verma",
            "phone": "9876543210",
            "loan_amount": 50000,
            "due_date": "2026-05-01",
            "overdue_days": 8,
            "late_fee": 500,
            "preferred_language": "en",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "session_created"
    assert data["session"]["customer"]["name"] == "Anita Verma"
    assert data["session"]["loan"]["loan_amount"] == 50000
    assert data["session"]["identity_verified"] is False


def test_process_identity_turn():
    session_id = create_demo_session()

    response = client.post(
        f"/api/calls/sessions/{session_id}/turns",
        json={
            "user_text": "Yes, I am Anita Verma speaking",
            "channel": "text",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "turn_processed"
    assert data["session"]["identity_verified"] is True
    assert data["result"]["agent_decision"]["selected_agent"] == "loan_servicing_agent"
    assert "₹50,000" in data["result"]["final_response"]


def test_process_payment_done_turn_after_identity():
    session_id = create_demo_session()

    client.post(
        f"/api/calls/sessions/{session_id}/turns",
        json={
            "user_text": "Yes, I am Anita Verma speaking",
            "channel": "text",
        },
    )

    response = client.post(
        f"/api/calls/sessions/{session_id}/turns",
        json={
            "user_text": "I already paid, transaction id is OKPAY123",
            "channel": "text",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["result"]["intent_result"]["intent"] == "payment_done"
    assert data["result"]["agent_decision"]["selected_agent"] == "payment_operations_agent"
    assert data["session"]["payment_status"] == "verified"


def test_decision_trace_endpoint():
    session_id = create_demo_session()

    client.post(
        f"/api/calls/sessions/{session_id}/turns",
        json={
            "user_text": "Yes, I am Anita Verma speaking",
            "channel": "text",
        },
    )

    client.post(
        f"/api/calls/sessions/{session_id}/turns",
        json={
            "user_text": "I cannot pay right now",
            "channel": "text",
        },
    )

    response = client.get(f"/api/calls/sessions/{session_id}/trace")

    assert response.status_code == 200

    data = response.json()

    assert data["trace_count"] >= 2
    assert "decision_trace" in data
    assert data["decision_trace"][-1]["detected_intent"] == "cannot_pay"


def test_unknown_session_returns_404():
    response = client.get("/api/calls/sessions/unknown-session")

    assert response.status_code == 404