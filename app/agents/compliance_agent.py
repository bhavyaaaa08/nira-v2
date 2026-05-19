from __future__ import annotations

import re

from app.core.enums import ComplianceStatus, PaymentStatus
from app.core.schemas import AgentResponse, ComplianceResult
from app.core.state import CallState


ACCOUNT_DETAIL_PATTERNS = [
    r"₹\s?\d+",
    r"\bloan payment\b",
    r"\bloan amount\b",
    r"\boverdue\b",
    r"\bdue date\b",
    r"\blate fee\b",
    r"\baccount\b",
]


COERCIVE_PHRASES = {
    "legal action",
    "police",
    "arrest",
    "criminal case",
    "court case",
    "blacklist",
    "cibil will be destroyed",
    "you will regret",
    "last warning",
    "severe consequences",
    "fraud case will be filed",
}


FALSE_PAYMENT_CONFIRMATION_PHRASES = {
    "payment is confirmed",
    "payment has been confirmed",
    "your account is closed",
    "loan is closed",
    "case is closed",
    "payment processed successfully",
}


RUDE_PHRASES = {
    "you are lying",
    "that is your problem",
    "you must pay now",
    "you have no choice",
    "stop making excuses",
}


class ComplianceAgent:
    """
    Compliance guardrail agent for NIRA.

    It checks whether a proposed response is safe to say to a banking customer.

    Main checks:
    - Do not reveal account details before identity verification.
    - Do not use coercive or threatening language.
    - Do not claim payment/account closure without verified status.
    - Do not use rude or argumentative language.
    - Keep responses suitable for customer operations.
    """

    def check(self, response_text: str, state: CallState) -> ComplianceResult:
        response = response_text or ""
        lower_response = response.lower()

        violations: list[str] = []

        if self._reveals_account_details_before_verification(response, state):
            violations.append("account_details_before_identity_verification")

        if self._contains_any(lower_response, COERCIVE_PHRASES):
            violations.append("coercive_or_threatening_language")

        if self._contains_any(lower_response, RUDE_PHRASES):
            violations.append("rude_or_argumentative_language")

        if self._makes_false_payment_claim(lower_response, state):
            violations.append("unverified_payment_or_account_closure_claim")

        if not violations:
            return ComplianceResult(
                status=ComplianceStatus.PASSED,
                violations=[],
                safe_response=None,
            )

        safe_response = self._safe_rewrite(violations, state)

        status = (
            ComplianceStatus.BLOCKED
            if "account_details_before_identity_verification" in violations
            else ComplianceStatus.NEEDS_REWRITE
        )

        return ComplianceResult(
            status=status,
            violations=violations,
            safe_response=safe_response,
        )

    def enforce(self, response: AgentResponse, state: CallState) -> AgentResponse:
        result = self.check(response.response_text, state)

        if result.status == ComplianceStatus.PASSED:
            return response

        response.response_text = result.safe_response or (
            "I am sorry, I cannot continue with that response. "
            "Let me connect this to the right team for review."
        )
        response.actions.append("compliance_rewrite_applied")
        response.metadata["compliance_result"] = result.model_dump()

        return response

    def _reveals_account_details_before_verification(
        self,
        response_text: str,
        state: CallState,
    ) -> bool:
        if state.identity_verified:
            return False

        return any(
            re.search(pattern, response_text, flags=re.IGNORECASE)
            for pattern in ACCOUNT_DETAIL_PATTERNS
        )

    def _makes_false_payment_claim(
        self,
        lower_response: str,
        state: CallState,
    ) -> bool:
        has_payment_confirmation = self._contains_any(
            lower_response,
            FALSE_PAYMENT_CONFIRMATION_PHRASES,
        )

        if not has_payment_confirmation:
            return False

        return state.payment_status != PaymentStatus.VERIFIED

    def _contains_any(self, text: str, phrases: set[str]) -> bool:
        return any(phrase in text for phrase in phrases)

    def _safe_rewrite(self, violations: list[str], state: CallState) -> str:
        if "account_details_before_identity_verification" in violations:
            customer_name = state.customer.name if state.customer else "the account holder"
            return (
                f"For security, I can only discuss account details after confirming I am "
                f"speaking with {customer_name}. Could you please confirm your identity?"
            )

        if "coercive_or_threatening_language" in violations:
            return (
                "I understand this situation may be difficult. I can help you review payment "
                "options or connect you to an executive for support."
            )

        if "unverified_payment_or_account_closure_claim" in violations:
            return (
                "Thank you. I can mark this for verification, but I cannot confirm the payment "
                "or close the account until verification is complete."
            )

        if "rude_or_argumentative_language" in violations:
            return (
                "I understand your concern. I will keep this professional and help route the "
                "issue to the right team."
            )

        return (
            "I understand. Let me handle this safely and route it to the right team for review."
        )