from __future__ import annotations

from app.agents.context_resolver_agent import ContextResolverAgent
from app.core.enums import AgentName, CallPhase, Intent, PendingAction
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
    - contextual confirmation of pending actions
    """

    def _is_hinglish(self, state: CallState) -> bool:
        return state.language.value in {"hi", "hinglish"}

    def __init__(self) -> None:
        self.context_resolver = ContextResolverAgent()

    def respond(self, state: CallState, intent_result: IntentResult) -> AgentResponse:
        context_resolution = self.context_resolver.resolve(state, intent_result)
        intent = intent_result.intent

        if intent == Intent.EXPLAIN_PENDING_ACTION:
            return self._handle_pending_action_explanation(state, context_resolution.pending_action)

        if intent == Intent.CONFIRM_PENDING_ACTION:
            return self._handle_pending_action_confirmation(state, context_resolution.pending_action)

        if intent == Intent.CANCEL_PENDING_ACTION:
            return self._handle_pending_action_cancellation(state, context_resolution.pending_action)

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

        state.clear_pending_action()
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
            f" by {commitment_time}"
            if commitment_time
            else ""
        )

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                f"Thank you. I have noted your payment commitment{amount_text}{time_text}. "
                "Please complete the payment through UPI, bank transfer, the loan app, or the payment portal. "
                "After payment, please keep the transaction reference for verification."
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

        state.clear_pending_action()
        state.outcome = "partial_payment_discussed"

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                f"Thank you for letting me know. I can note that you are able to pay {amount_text}. "
                "Partial payment may reduce the pending balance, but the remaining amount can still stay overdue. "
                "When will you be able to pay the remaining amount?"
            ),
            next_phase=CallPhase.SERVICING,
            outcome="partial_payment_discussed",
            actions=["record_partial_payment_intent"],
            metadata={"partial_amount": amount},
        )

    def _handle_cannot_pay(self, state: CallState) -> AgentResponse:
        state.outcome = "extension_review_offered"
        state.set_pending_action(
            PendingAction.CONFIRM_EXTENSION_REVIEW,
            {
                "reason": "customer_cannot_pay",
                "source": "loan_servicing_agent",
            },
        )

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "I understand. I can raise a request for an executive to review possible "
                "extension or restructuring options. Would you like me to raise that request?"
            ),
            next_phase=CallPhase.SERVICING,
            outcome="extension_review_offered",
            actions=["offer_extension_review"],
            metadata={
                "pending_action": PendingAction.CONFIRM_EXTENSION_REVIEW.value,
            },
        )

    def _handle_extension_request(self, state: CallState) -> AgentResponse:
        state.outcome = "extension_review_offered"
        state.set_pending_action(
            PendingAction.CONFIRM_EXTENSION_REVIEW,
            {
                "reason": "customer_requested_extension",
                "source": "loan_servicing_agent",
            },
        )

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "I understand that you need more time. I cannot approve an extension myself, "
                "but I can raise a request for executive review. Would you like me to raise it?"
            ),
            next_phase=CallPhase.SERVICING,
            outcome="extension_review_offered",
            actions=["offer_extension_review"],
            metadata={
                "pending_action": PendingAction.CONFIRM_EXTENSION_REVIEW.value,
            },
        )

    def _handle_penalty_question(self, state: CallState) -> AgentResponse:
        loan = state.loan
        late_fee = loan.late_fee if loan else None

        fee_text = (
            f"₹{late_fee:.0f}"
            if late_fee
            else "the applicable late fee"
        )

        overdue_text = (
            f" because the payment was not received by the due date and is {loan.overdue_days} days overdue"
            if loan and loan.overdue_days > 0
            else " because the payment was not received by the due date"
        )

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                f"The late fee is {fee_text}. It applies{overdue_text}, as per the loan terms. "
                "You can still make the payment through the approved payment channels."
            ),
            next_phase=CallPhase.SERVICING,
            actions=["explain_late_fee"],
        )

    def _handle_waiver_request(self, state: CallState) -> AgentResponse:
        loan = state.loan
        late_fee = loan.late_fee if loan and loan.late_fee else None

        fee_text = (
            f"₹{late_fee:.0f}"
            if late_fee
            else "the late fee"
        )

        state.outcome = "waiver_review_offered"
        state.set_pending_action(
            PendingAction.CONFIRM_WAIVER_REVIEW,
            {
                "late_fee": late_fee,
                "source": "loan_servicing_agent",
            },
        )

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                f"I understand you would like a waiver for {fee_text}. "
                "I cannot guarantee approval, but I can raise a late-fee waiver request for review. "
                "Approval will depend on bank policy, repayment history, and account eligibility. "
                "Would you like me to raise this request?"
            ),
            next_phase=CallPhase.SERVICING,
            outcome="waiver_review_offered",
            actions=["offer_waiver_review_request"],
            metadata={
                "late_fee": late_fee,
                "pending_action": PendingAction.CONFIRM_WAIVER_REVIEW.value,
            },
        )

    def _handle_payment_method(self, state: CallState) -> AgentResponse:
        state.clear_pending_action()

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "You can pay through UPI, bank transfer, the loan app, or the lender payment portal. "
                "After payment, please keep the transaction reference for verification."
            ),
            next_phase=CallPhase.PAYMENT,
            actions=["share_payment_methods"],
        )

    def _handle_pending_action_confirmation(
        self,
        state: CallState,
        pending_action: PendingAction | None,
    ) -> AgentResponse:
        if pending_action == PendingAction.CONFIRM_WAIVER_REVIEW:
            return self._handle_waiver_confirmation(state)

        if pending_action == PendingAction.CONFIRM_EXTENSION_REVIEW:
            return self._handle_extension_confirmation(state)

        if pending_action == PendingAction.CONFIRM_ESCALATION:
            return self._handle_escalation_confirmation(state)

        state.clear_pending_action()

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "Thank you for confirming. I have noted your request and will mark it for review."
            ),
            next_phase=CallPhase.SERVICING,
            outcome="pending_action_confirmed",
            actions=["confirm_pending_action"],
        )

    def _handle_pending_action_cancellation(
        self,
        state: CallState,
        pending_action: PendingAction | None,
    ) -> AgentResponse:
        cancelled_action = pending_action.value if pending_action else None
        state.clear_pending_action()
        state.outcome = "pending_action_cancelled"

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "Okay, I will not raise that request. I can still help with payment methods, "
                "late fee details, waiver review, or extension options."
            ),
            next_phase=CallPhase.SERVICING,
            outcome="pending_action_cancelled",
            actions=["cancel_pending_action"],
            metadata={
                "cancelled_action": cancelled_action,
            },
        )

    def _handle_waiver_confirmation(self, state: CallState) -> AgentResponse:
        loan = state.loan
        late_fee = loan.late_fee if loan and loan.late_fee else None

        fee_text = (
            f"₹{late_fee:.0f}"
            if late_fee
            else "the late fee"
        )

        state.clear_pending_action()
        state.outcome = "waiver_review_requested"

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                f"Done. I have raised a late-fee waiver review request for {fee_text}. "
                "The final decision will depend on bank policy and account eligibility."
            ),
            next_phase=CallPhase.ESCALATION,
            outcome="waiver_review_requested",
            actions=["raise_waiver_review_request"],
            metadata={
                "late_fee": late_fee,
            },
        )

    def _handle_extension_confirmation(self, state: CallState) -> AgentResponse:
        state.clear_pending_action()
        state.outcome = "extension_review_requested"
        state.mark_escalation()

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "Done. I have raised an executive review request for possible extension or restructuring options. "
                "The final decision will depend on bank policy and account eligibility."
            ),
            next_phase=CallPhase.ESCALATION,
            outcome="extension_review_requested",
            actions=["raise_extension_review_request"],
        )

    def _handle_escalation_confirmation(self, state: CallState) -> AgentResponse:
        state.clear_pending_action()
        state.mark_escalation()

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "Done. I have marked this for executive escalation. A support executive will review the case."
            ),
            next_phase=CallPhase.ESCALATION,
            outcome="escalated",
            actions=["confirm_escalation"],
        )

    def _handle_closing(self, state: CallState) -> AgentResponse:
        state.clear_pending_action()
        state.close(outcome=state.outcome or "customer_closed_call")

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text="Thank you for your time. Have a good day.",
            next_phase=CallPhase.POST_CALL,
            outcome=state.outcome,
            actions=["close_call"],
        )

    def _handle_general_servicing(self, state: CallState) -> AgentResponse:
        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=(
                "I can help with your loan payment, due amount, payment method, late fee, "
                "waiver request, or extension request. What would you like help with?"
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
        readable_date = self._readable_date(date_text)
        readable_time = self._readable_time(time_text)

        if readable_date and readable_time:
            return f"{readable_date} {readable_time}"

        if readable_date:
            return readable_date

        if readable_time:
            return readable_time

        return None

    def _readable_date(self, date_text: str | None) -> str | None:
        if not date_text:
            return None

        mapping = {
            "today": "today",
            "tomorrow": "tomorrow",
            "yesterday": "yesterday",
            "day_after_tomorrow": "day after tomorrow",
            "next_week": "next week",
            "end_of_week": "the end of this week",
            "monday": "Monday",
            "tuesday": "Tuesday",
            "wednesday": "Wednesday",
            "thursday": "Thursday",
            "friday": "Friday",
            "saturday": "Saturday",
            "sunday": "Sunday",
        }

        return mapping.get(date_text, date_text)

    def _readable_time(self, time_text: str | None) -> str | None:
        if not time_text:
            return None

        mapping = {
            "morning": "in the morning",
            "afternoon": "in the afternoon",
            "evening": "in the evening",
            "night": "at night",
        }

        return mapping.get(time_text, time_text)
    
    def _handle_pending_action_explanation(
    self,
    state: CallState,
    pending_action: PendingAction | None,
) -> AgentResponse:
        if pending_action == PendingAction.CONFIRM_EXTENSION_REVIEW:
            response_text = (
                "It means I can raise your case for executive review. "
                "The executive team may check if extension or restructuring is possible, "
                "but approval is not guaranteed. Would you like me to raise this request?"
            )
        elif pending_action == PendingAction.CONFIRM_WAIVER_REVIEW:
            response_text = (
                "It means I can raise your late-fee waiver request for review. "
                "The bank will check policy, repayment history, and eligibility. "
                "Approval is not guaranteed. Would you like me to raise it?"
            )
        else:
            response_text = (
                "It means I can mark your request for review by the right team. "
                "Would you like me to continue?"
            )

        return AgentResponse(
            agent_name=AgentName.LOAN_SERVICING,
            response_text=response_text,
            next_phase=CallPhase.SERVICING,
            outcome=state.outcome,
            actions=["explain_pending_action"],
        )