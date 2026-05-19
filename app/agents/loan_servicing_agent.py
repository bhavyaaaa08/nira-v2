from __future__ import annotations

from app.core.enums import AgentName, CallPhase, Intent
from app.core.schemas import AgentResponse, IntentResult
from app.core.state import CallState


class LoanServicingAgent:
    """
    Handles loan servicing conversations:
    - due amount explanation
    - overdue reminder
    - promise-to-pay
    - cannot-pay situations
    - extension request
    - late fee question
    - waiver request
    - partial payment
    """

    def respond(self, state: CallState, intent_result: IntentResult) -> AgentResponse:
        intent = intent_result.intent

        if intent == Intent.PROMISE_TO_PAY:
            return self._handle_promise_to_pay(state, intent_result)

        if intent == Intent.PARTIAL_PAYMENT:
            return self._handle_partial_payment(state, intent_result)

        if intent == Intent.CANNOT_PAY:
            return self._handle_cannot_pay(state)

        if intent == Intent.NEEDS_EXTENSION:
            return self._handle_extension_request(state)

        if intent == Intent.PENALTY_QUESTION:
            return self._handle_penalty_question(state)

        if intent == Intent.WAIVER_REQUEST:
            return self._handle_waiver_request(state)

        if intent == Intent.PAYMENT_METHOD:
            return self._handle_payment_method(state)

        if intent == Intent.CLOSING:
            return self._handle_closing(state)

        return self._handle_general_servicing(state)

    def initial_briefing(self, state: CallState) -> AgentResponse:
        customer_name = self._customer_name(state)
        loan = state.loan

        if loan is None:
            return AgentResponse(
                agent_name=AgentName.LOAN_SERVICING,
                response_text=(
                    "Thank you for confirming. I am unable to find an active loan account right now, "
                    "so I will flag this for review."
                ),
                next_phase=CallPhase.ESCALATION,
                actions=["flag_missing_loan_account"],
            )

        if loan.overdue_days > 0:
            late_fee_text = (
                f" A late fee of ₹{loan.late_fee:.0f} has also been applied."
                if loan.late_fee
                else ""
            )
            response = (
                f"Thank you for confirming, {customer_name}. Your loan payment of "
                f"₹{loan.loan_amount:,.0f} was due on {loan.due_date} and is "
                f"{loan.overdue_days} days overdue.{late_fee_text} "
                "When do you think you can make the payment?"
            )
        else:
            response = (
                f"Thank you for confirming, {customer_name}. Your loan payment of "
                f"₹{loan.loan_amount:,.0f} is due on {loan.due_date}. "
                "When do you plan to make the payment?"
            )

        state.advance_to(CallPhase.SERVICING)

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=response,
            next_phase=CallPhase.SERVICING,
            actions=["deliver_account_briefing"],
        )

    def _handle_promise_to_pay(
        self,
        state: CallState,
        intent_result: IntentResult,
    ) -> AgentResponse:
        entities = intent_result.entities

        commitment_time = self._format_commitment_time(
            date_text=entities.date,
            time_text=entities.time,
        )

        state.mark_commitment(
            time_text=commitment_time,
            amount=entities.amount,
        )

        amount_text = (
            f" for ₹{entities.amount:,.0f}"
            if entities.amount
            else ""
        )

        time_text = (
            f" {commitment_time}"
            if commitment_time
            else ""
        )

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                f"Thank you. I have noted your payment commitment{amount_text}{time_text}. "
                "You can pay through UPI, bank transfer, the loan app, or the payment portal."
            ),
            next_phase=CallPhase.PAYMENT,
            outcome="promise_to_pay",
            actions=["record_promise_to_pay", "schedule_follow_up"],
            metadata={
                "commitment_time": commitment_time,
                "commitment_amount": entities.amount,
            },
        )

    def _handle_partial_payment(
        self,
        state: CallState,
        intent_result: IntentResult,
    ) -> AgentResponse:
        amount = intent_result.entities.amount

        amount_text = (
            f"₹{amount:,.0f}"
            if amount
            else "a partial amount"
        )

        state.outcome = "partial_payment_discussed"

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                f"Thank you for letting me know. I can note that you are able to pay {amount_text}. "
                "When will you be able to pay the remaining amount?"
            ),
            next_phase=CallPhase.SERVICING,
            outcome="partial_payment_discussed",
            actions=["record_partial_payment_intent"],
            metadata={"partial_amount": amount},
        )

    def _handle_cannot_pay(self, state: CallState) -> AgentResponse:
        state.outcome = "needs_extension_review"

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "I understand. I can connect you to an executive who can review possible "
                "extension or restructuring options. Would you like me to raise that request?"
            ),
            next_phase=CallPhase.ESCALATION,
            outcome="needs_extension_review",
            actions=["offer_extension_review"],
        )

    def _handle_extension_request(self, state: CallState) -> AgentResponse:
        state.outcome = "extension_requested"

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "I understand that you need more time. I cannot approve an extension myself, "
                "but I can raise a request for executive review."
            ),
            next_phase=CallPhase.ESCALATION,
            outcome="extension_requested",
            actions=["raise_extension_review_request"],
        )

    def _handle_penalty_question(self, state: CallState) -> AgentResponse:
        loan = state.loan
        late_fee = loan.late_fee if loan else None

        fee_text = (
            f"₹{late_fee:.0f}"
            if late_fee
            else "the applicable late fee"
        )

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                f"The late fee is {fee_text}. It applies because the payment was not received "
                "by the due date as per the loan terms."
            ),
            next_phase=CallPhase.SERVICING,
            actions=["explain_late_fee"],
        )

    def _handle_waiver_request(self, state: CallState) -> AgentResponse:
        state.outcome = "waiver_review_requested"

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "I can raise a late-fee waiver request for review, but approval depends on "
                "executive review and bank policy."
            ),
            next_phase=CallPhase.ESCALATION,
            outcome="waiver_review_requested",
            actions=["raise_waiver_review_request"],
        )

    def _handle_payment_method(self, state: CallState) -> AgentResponse:
        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "You can pay through UPI, bank transfer, the loan app, or the lender payment portal. "
                "After payment, please keep the transaction reference for verification."
            ),
            next_phase=CallPhase.PAYMENT,
            actions=["share_payment_methods"],
        )

    def _handle_closing(self, state: CallState) -> AgentResponse:
        state.close(outcome=state.outcome or "customer_closed_call")

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "Thank you for your time. Have a good day."
            ),
            next_phase=CallPhase.POST_CALL,
            outcome=state.outcome,
            actions=["close_call"],
        )

    def _handle_general_servicing(self, state: CallState) -> AgentResponse:
        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "I can help with your loan payment, due amount, payment method, late fee, "
                "or extension request. What would you like help with?"
            ),
            next_phase=CallPhase.SERVICING,
            actions=["continue_servicing"],
        )

    def _customer_name(self, state: CallState) -> str:
        if state.customer:
            return state.customer.name
        return "there"

    def _format_commitment_time(
        self,
        date_text: str | None,
        time_text: str | None,
    ) -> str | None:
        if date_text and time_text:
            return f"for {date_text} {time_text}"

        if date_text:
            return f"for {date_text}"

        if time_text:
            return f"for {time_text}"

        return None