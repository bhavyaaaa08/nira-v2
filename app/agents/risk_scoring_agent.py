from __future__ import annotations

from typing import Optional

from app.core.enums import Intent, RiskLevel
from app.core.schemas import IntentResult, LoanAccount, RiskResult
from app.core.state import CallState


HIGH_FRUSTRATION_PHRASES = {
    "stop calling",
    "harassment",
    "i will complain",
    "consumer court",
    "legal action",
    "lawsuit",
    "ridiculous",
    "nonsense",
    "pathetic",
    "useless",
    "fed up",
    "fraud",
    "scam",
    "baar baar",
    "pareshan",
    "mat karo",
    "band karo",
    "complaint",
    "court",
}


MILD_FRUSTRATION_PHRASES = {
    "already told you",
    "again and again",
    "not now",
    "busy",
    "irritating",
    "annoying",
    "how many times",
    "pehle bhi bola",
    "abhi nahi",
    "kyun call",
    "kya kaam",
}


def clamp_score(score: int) -> int:
    return max(0, min(100, score))


def risk_level_from_score(score: int) -> RiskLevel:
    if score >= 85:
        return RiskLevel.CRITICAL

    if score >= 60:
        return RiskLevel.HIGH

    if score >= 30:
        return RiskLevel.MEDIUM

    return RiskLevel.LOW


def compute_frustration_score(user_text: str) -> float:
    text = (user_text or "").lower().strip()
    score = 0.0

    if any(phrase in text for phrase in HIGH_FRUSTRATION_PHRASES):
        score += 0.70

    if any(phrase in text for phrase in MILD_FRUSTRATION_PHRASES):
        score += 0.30

    if "!!" in text or "???" in text:
        score += 0.15

    return round(min(score, 1.0), 2)


class RiskScoringAgent:
    """
    Risk scoring agent for NIRA.

    It evaluates operational risk for the current customer turn using:
    - overdue days
    - loan amount
    - detected intent
    - complaint/dispute/fraud signals
    - payment commitment
    - frustration score
    - call state flags

    Output:
    - score from 0 to 100
    - risk level
    - reasons
    - recommended next action
    """

    def analyze(
        self,
        state: CallState,
        intent_result: Optional[IntentResult] = None,
        user_text: str = "",
        update_state: bool = True,
    ) -> RiskResult:
        score = 0
        reasons: list[str] = []

        loan = state.loan
        intent = intent_result.intent if intent_result else state.last_intent

        score += self._score_loan_risk(loan, reasons)
        score += self._score_intent_risk(intent, reasons)
        score += self._score_state_risk(state, reasons)

        frustration_score = compute_frustration_score(user_text)
        state.frustration_score = frustration_score

        if frustration_score >= 0.70:
            score += 25
            reasons.append("Customer appears highly frustrated.")
        elif frustration_score >= 0.30:
            score += 10
            reasons.append("Customer appears mildly frustrated.")

        if state.commitment_received:
            score -= 15
            reasons.append("Payment commitment already received, reducing risk.")

        if state.payment_status.value == "verified":
            score -= 30
            reasons.append("Payment is verified, reducing operational risk.")

        final_score = clamp_score(score)
        level = risk_level_from_score(final_score)
        recommended_action = self._recommend_action(level, intent, state)

        result = RiskResult(
            score=final_score,
            level=level,
            reasons=reasons,
            recommended_action=recommended_action,
        )

        if update_state:
            state.risk_score = result.score
            state.risk_level = result.level

        return result

    def _score_loan_risk(
        self,
        loan: Optional[LoanAccount],
        reasons: list[str],
    ) -> int:
        if loan is None:
            return 0

        score = 0

        if loan.overdue_days > 30:
            score += 35
            reasons.append("Loan is overdue by more than 30 days.")
        elif loan.overdue_days > 7:
            score += 20
            reasons.append("Loan is overdue by more than 7 days.")
        elif loan.overdue_days > 0:
            score += 10
            reasons.append("Loan is overdue.")

        if loan.loan_amount >= 100000:
            score += 15
            reasons.append("Loan amount is high.")
        elif loan.loan_amount >= 50000:
            score += 10
            reasons.append("Loan amount is moderately high.")
        elif loan.loan_amount >= 10000:
            score += 5
            reasons.append("Loan amount is non-trivial.")

        return score

    def _score_intent_risk(
        self,
        intent: Intent,
        reasons: list[str],
    ) -> int:
        intent_scores = {
            Intent.PROMISE_TO_PAY: -10,
            Intent.PAYMENT_DONE: -5,
            Intent.PAYMENT_METHOD: -5,
            Intent.PARTIAL_PAYMENT: 10,
            Intent.CANNOT_PAY: 25,
            Intent.NEEDS_EXTENSION: 20,
            Intent.PENALTY_QUESTION: 5,
            Intent.WAIVER_REQUEST: 10,
            Intent.KYC_UPDATE: 5,
            Intent.COMPLAINT: 25,
            Intent.DISPUTE: 30,
            Intent.FRAUD_CLAIM: 40,
            Intent.ESCALATION_REQUEST: 25,
            Intent.CLOSING: 0,
            Intent.GENERAL: 0,
            Intent.UNKNOWN: 5,
        }

        score = intent_scores.get(intent, 0)

        reason_map = {
            Intent.PROMISE_TO_PAY: "Customer has promised to pay.",
            Intent.PAYMENT_DONE: "Customer claims payment is already done.",
            Intent.PAYMENT_METHOD: "Customer is asking how to pay.",
            Intent.PARTIAL_PAYMENT: "Customer is offering partial payment.",
            Intent.CANNOT_PAY: "Customer says they cannot pay currently.",
            Intent.NEEDS_EXTENSION: "Customer needs an extension.",
            Intent.PENALTY_QUESTION: "Customer is questioning late fee or penalty.",
            Intent.WAIVER_REQUEST: "Customer requested fee waiver.",
            Intent.KYC_UPDATE: "Customer requested KYC update.",
            Intent.COMPLAINT: "Customer raised a complaint.",
            Intent.DISPUTE: "Customer is disputing the loan or amount.",
            Intent.FRAUD_CLAIM: "Customer raised a possible fraud claim.",
            Intent.ESCALATION_REQUEST: "Customer requested human escalation.",
            Intent.UNKNOWN: "Intent is unclear.",
        }

        if intent in reason_map:
            reasons.append(reason_map[intent])

        return score

    def _score_state_risk(
        self,
        state: CallState,
        reasons: list[str],
    ) -> int:
        score = 0

        if state.dispute_registered:
            score += 20
            reasons.append("Dispute is already registered in this session.")

        if state.complaint_registered:
            score += 15
            reasons.append("Complaint is already registered in this session.")

        if state.escalation_required:
            score += 20
            reasons.append("Escalation is already required.")

        if state.identity_attempts >= 2 and not state.identity_verified:
            score += 10
            reasons.append("Identity verification required multiple attempts.")

        return score

    def _recommend_action(
        self,
        level: RiskLevel,
        intent: Intent,
        state: CallState,
    ) -> str:
        if intent == Intent.FRAUD_CLAIM:
            return "Create fraud review ticket and escalate to specialist team."

        if intent == Intent.DISPUTE:
            return "Create dispute ticket and avoid arguing about the amount."

        if intent == Intent.COMPLAINT:
            return "Register complaint and reduce repeated contact."

        if intent == Intent.CANNOT_PAY:
            return "Offer executive review for extension or restructuring."

        if intent == Intent.PROMISE_TO_PAY:
            return "Record promise-to-pay and schedule follow-up reminder."

        if intent == Intent.PAYMENT_DONE:
            return "Ask for transaction reference and start payment verification."

        if level == RiskLevel.CRITICAL:
            return "Immediate human escalation recommended."

        if level == RiskLevel.HIGH:
            return "Prioritize for follow-up and offer human escalation if needed."

        if level == RiskLevel.MEDIUM:
            return "Continue guided servicing and monitor for escalation."

        return "Continue normal servicing."