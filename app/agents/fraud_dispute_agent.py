from __future__ import annotations

from app.core.enums import AgentName, CallPhase, Intent, RiskLevel, TicketCategory
from app.core.schemas import AgentResponse, IntentResult, Ticket
from app.core.state import CallState


class FraudDisputeAgent:
    """
    Handles fraud and dispute cases:
    - customer denies taking the loan
    - wrong amount
    - not my loan
    - unauthorized loan
    - suspected fraud
    - payment not reflected dispute

    This agent must not argue with the customer.
    It should acknowledge, flag for review, and escalate safely.
    """

    def respond(self, state: CallState, intent_result: IntentResult) -> AgentResponse:
        intent = intent_result.intent

        if intent == Intent.FRAUD_CLAIM:
            return self._handle_fraud_claim(state, intent_result)

        return self._handle_dispute(state, intent_result)

    def _handle_fraud_claim(
        self,
        state: CallState,
        intent_result: IntentResult,
    ) -> AgentResponse:
        state.mark_dispute()
        state.mark_escalation()

        reason = (
            intent_result.entities.dispute_reason
            or state.last_user_text
            or "Customer raised possible fraud claim."
        )

        ticket = self.create_ticket(
            state=state,
            reason=reason,
            category=TicketCategory.FRAUD,
            prefix="FRAUD",
            assigned_team="fraud_review_team",
            priority=RiskLevel.CRITICAL,
        )

        return AgentResponse(
            agent_name=AgentName.FRAUD_DISPUTE,
            response_text=(
                f"I understand your concern. I have flagged this as a possible fraud case "
                f"with ticket ID {ticket.ticket_id}, and it will be reviewed by the fraud team."
            ),
            next_phase=CallPhase.ESCALATION,
            outcome="fraud_review_registered",
            actions=[
                "create_fraud_ticket",
                "escalate_to_fraud_team",
                "pause_normal_collection_followup",
            ],
            metadata={
                "ticket": ticket.model_dump(),
            },
        )

    def _handle_dispute(
        self,
        state: CallState,
        intent_result: IntentResult,
    ) -> AgentResponse:
        state.mark_dispute()
        state.advance_to(CallPhase.DISPUTE)

        reason = (
            intent_result.entities.dispute_reason
            or state.last_user_text
            or "Customer disputed the loan or amount."
        )

        ticket = self.create_ticket(
            state=state,
            reason=reason,
            category=TicketCategory.DISPUTE,
            prefix="DISP",
            assigned_team="dispute_resolution_team",
            priority=RiskLevel.HIGH if state.risk_level == RiskLevel.LOW else state.risk_level,
        )

        return AgentResponse(
            agent_name=AgentName.FRAUD_DISPUTE,
            response_text=(
                f"I understand your concern. I have created dispute ticket {ticket.ticket_id} "
                f"for review, and the team will investigate the account details."
            ),
            next_phase=CallPhase.DISPUTE,
            outcome="dispute_registered",
            actions=[
                "create_dispute_ticket",
                "flag_account_for_review",
                "avoid_argument_with_customer",
            ],
            metadata={
                "ticket": ticket.model_dump(),
            },
        )

    def create_ticket(
        self,
        state: CallState,
        reason: str,
        category: TicketCategory,
        prefix: str,
        assigned_team: str,
        priority: RiskLevel,
    ) -> Ticket:
        ticket_id = self._generate_ticket_id(state, prefix)

        return Ticket(
            ticket_id=ticket_id,
            customer_id=state.customer.customer_id if state.customer else None,
            session_id=state.session_id,
            category=category,
            priority=priority,
            summary=reason,
            assigned_team=assigned_team,
        )

    def _generate_ticket_id(self, state: CallState, prefix: str) -> str:
        short_session = state.session_id.split("-")[0].upper()
        return f"{prefix}-{short_session}"