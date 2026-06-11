from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


DATA_DIR = Path("data")


def load_csv(filename: str) -> list[dict[str, Any]]:
    path = DATA_DIR / filename

    if not path.exists():
        return []

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def get_customers() -> list[dict[str, Any]]:
    return load_csv("customers.csv")


def get_loans() -> list[dict[str, Any]]:
    return load_csv("loans.csv")


def get_payments() -> list[dict[str, Any]]:
    return load_csv("payments.csv")


def get_customer_by_phone(phone: str) -> dict[str, Any] | None:
    normalized_phone = str(phone).strip()

    for customer in get_customers():
        if str(customer.get("phone", "")).strip() == normalized_phone:
            return customer

    return None


def get_customer_by_id(customer_id: str | int) -> dict[str, Any] | None:
    target_id = str(customer_id).strip()

    for customer in get_customers():
        if str(customer.get("customer_id", "")).strip() == target_id:
            return customer

    return None


def get_loan_for_customer(customer_id: str | int) -> dict[str, Any] | None:
    target_id = str(customer_id).strip()

    for loan in get_loans():
        if str(loan.get("customer_id", "")).strip() == target_id:
            return loan

    return None


def get_payments_for_customer(customer_id: str | int) -> list[dict[str, Any]]:
    target_id = str(customer_id).strip()

    return [
        payment
        for payment in get_payments()
        if str(payment.get("customer_id", "")).strip() == target_id
    ]


def get_demo_profiles() -> list[dict[str, Any]]:
    profiles = []

    for customer in get_customers():
        customer_id = customer.get("customer_id")
        loan = get_loan_for_customer(customer_id)
        payments = get_payments_for_customer(customer_id)

        profiles.append(
            {
                "customer": customer,
                "loan": loan,
                "payments": payments,
                "tickets": get_tickets_for_customer(customer_id),
                "commitments": get_commitments_for_customer(customer_id),
            }
        )

    return profiles

def get_seed_tickets() -> list[dict[str, Any]]:
    return load_csv("tickets.csv")


def get_seed_commitments() -> list[dict[str, Any]]:
    return load_csv("payment_commitments.csv")


def get_tickets_for_customer(customer_id: str | int) -> list[dict[str, Any]]:
    target_id = str(customer_id).strip()

    return [
        ticket
        for ticket in get_seed_tickets()
        if str(ticket.get("customer_id", "")).strip() == target_id
    ]


def get_commitments_for_customer(customer_id: str | int) -> list[dict[str, Any]]:
    target_id = str(customer_id).strip()

    return [
        commitment
        for commitment in get_seed_commitments()
        if str(commitment.get("customer_id", "")).strip() == target_id
    ]

if __name__ == "__main__":
    for profile in get_demo_profiles():
        print(profile)