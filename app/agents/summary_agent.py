from __future__ import annotations

from app.core.enums import AgentName, PaymentStatus
from app.core.schemas import CallSummary
from app.core.state import CallState


class SummaryAgent:
    """
    Generates deterministic post-call summaries.

    This is intentionally rule-based for now.
    Later, Gemini/Groq can polish `summary_text`, but the facts should still
    come from CallState.
    """

    agent_name = AgentName.SUMMARY

    def summarize(self, state: CallState) -> CallSummary:
        key_events = self._build_key_events(state)
        next_actions = self._build_next_actions(state)
        customer_commitment = self._build_customer_commitment(state)
        summary_text = self._build_summary_text(
            state=state,
            key_events=key_events,
            next_actions=next_actions,
        )

        return CallSummary(
            session_id=state.session_id,
            customer_name=state.customer.name if state.customer else None,
            phone=state.customer.phone if state.customer else None,
            phase=state.phase,
            identity_verified=state.identity_verified,
            risk_score=state.risk_score,
            risk_level=state.risk_level,
            payment_status=state.payment_status,
            outcome=state.outcome,
            outcome_detail=state.outcome_detail,
            summary_text=summary_text,
            key_events=key_events,
            next_actions=next_actions,
            customer_commitment=customer_commitment,
        )

    def _build_key_events(self, state: CallState) -> list[str]:
        events: list[str] = []

        if state.identity_verified:
            events.append("Customer identity was verified.")
        else:
            events.append("Customer identity was not verified.")

        if state.loan:
            events.append(
                f"Loan amount is ₹{state.loan.loan_amount:,.0f}, due on {state.loan.due_date}."
            )

            if state.loan.overdue_days > 0:
                events.append(f"Loan is {state.loan.overdue_days} days overdue.")

            if state.loan.late_fee:
                events.append(f"Late fee applied is ₹{state.loan.late_fee:,.0f}.")

        if state.commitment_received:
            commitment = state.commitment_time or "a future time"
            amount = (
                f" for ₹{state.commitment_amount:,.0f}"
                if state.commitment_amount
                else ""
            )
            events.append(f"Customer gave a payment commitment{amount} by {commitment}.")

        if state.payment_status == PaymentStatus.VERIFIED:
            events.append("Payment was verified successfully.")
        elif state.payment_status == PaymentStatus.VERIFICATION_PENDING:
            events.append("Payment verification is pending.")
        elif state.payment_status == PaymentStatus.FAILED:
            events.append("Payment verification failed.")
        elif state.payment_status == PaymentStatus.TRANSACTION_NOT_FOUND:
            events.append("Transaction reference was not found.")
        elif state.payment_status == PaymentStatus.AMOUNT_MISMATCH:
            events.append("Payment amount mismatch was detected.")

        if state.complaint_registered:
            events.append("Complaint was registered.")

        if state.dispute_registered:
            events.append("Dispute or fraud review was registered.")

        if state.kyc_request_registered:
            events.append("KYC update request was registered.")

        if state.escalation_required:
            events.append("Case was marked for escalation or executive review.")

        if state.outcome:
            events.append(f"Final outcome: {state.outcome}.")

        return events

    def _build_next_actions(self, state: CallState) -> list[str]:
        actions: list[str] = []

        if not state.identity_verified:
            actions.append("Verify customer identity before discussing account details.")
            return actions

        if state.outcome == "promise_to_pay":
            actions.append("Track promised payment date and follow up if payment is not received.")
            actions.append("Verify transaction reference after customer completes payment.")

        elif state.outcome in {
            "extension_review_requested",
            "needs_extension_review",
            "extension_requested",
        }:
            actions.append("Executive team should review extension or restructuring eligibility.")
            actions.append("Update customer after review decision.")

        elif state.outcome == "waiver_review_requested":
            actions.append("Executive team should review late-fee waiver eligibility.")
            actions.append("Update customer after waiver review decision.")

        elif state.outcome == "complaint_registered":
            actions.append("Support team should review and resolve the complaint ticket.")

        elif state.outcome == "dispute_registered":
            actions.append("Dispute team should investigate the customer claim.")

        elif state.outcome == "kyc_update_requested":
            actions.append("KYC team should verify documents and process the update.")

        elif state.payment_status == PaymentStatus.VERIFICATION_PENDING:
            actions.append("Payment operations team should verify the submitted transaction reference.")

        elif state.payment_status == PaymentStatus.VERIFIED:
            actions.append("No immediate payment follow-up needed. Mark account accordingly.")

        elif state.phase.value == "post_call":
            actions.append("Call is closed. Review outcome and trace if needed.")

        else:
            actions.append("Continue follow-up based on customer response and account status.")

        return actions

    def _build_customer_commitment(self, state: CallState) -> str | None:
        if not state.commitment_received:
            return None

        amount_text = (
            f"₹{state.commitment_amount:,.0f}"
            if state.commitment_amount
            else "payment"
        )

        time_text = state.commitment_time or "committed time"

        return f"{amount_text} by {time_text}"

    def _build_summary_text(
        self,
        state: CallState,
        key_events: list[str],
        next_actions: list[str],
    ) -> str:
        customer_name = state.customer.name if state.customer else "The customer"

        outcome_text = state.outcome or "not decided"
        risk_text = f"{state.risk_level.value} risk with score {state.risk_score}/100"

        event_sentence = " ".join(key_events[:4])
        action_sentence = " ".join(next_actions[:2])

        return (
            f"{customer_name} completed a NIRA banking assistance call. "
            f"The current outcome is {outcome_text}. "
            f"The case is classified as {risk_text}. "
            f"{event_sentence} "
            f"Recommended next action: {action_sentence}"
        )