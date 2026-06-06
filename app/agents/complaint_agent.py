from __future__ import annotations

from app.core.enums import AgentName, CallPhase, RiskLevel, TicketCategory
from app.core.schemas import AgentResponse, IntentResult, Ticket
from app.core.state import CallState

from app.services.operations_store import operations_store


class ComplaintAgent:
    """
    Handles customer complaints:
    - repeated calls
    - rude experience
    - wrong information
    - app/payment issues
    - late fee dissatisfaction
    - service complaints
    """

    def respond(self, state: CallState, intent_result: IntentResult) -> AgentResponse:
        state.mark_complaint()
        state.advance_to(CallPhase.COMPLAINT)

        complaint_reason = (
            intent_result.entities.complaint_reason
            or state.last_user_text
            or "Customer raised a complaint."
        )

        ticket = self.create_ticket(state, complaint_reason)

        operations_store.create_ticket(
            ticket_id=ticket.ticket_id,
            session_id=state.session_id,
            customer_name=state.customer.name if state.customer else None,
            phone=state.customer.phone if state.customer else None,
            category=ticket.category.value,
            priority=ticket.priority.value,
            status=ticket.status.value,
            summary=ticket.summary,
            assigned_team=ticket.assigned_team,
            source_agent=AgentName.COMPLAINT.value,
            metadata=ticket.model_dump(),
        )

        return AgentResponse(
            agent_name=AgentName.COMPLAINT,
            response_text=(
                f"I am sorry for the inconvenience. I have registered your complaint "
                f"with ticket ID {ticket.ticket_id}, and it will be reviewed by the support team."
            ),
            next_phase=CallPhase.COMPLAINT,
            outcome="complaint_registered",
            actions=[
                "create_complaint_ticket",
                "reduce_repeated_contact",
                "notify_support_team",
            ],
            metadata={
                "ticket": ticket.model_dump(),
            },
        )

    def create_ticket(self, state: CallState, complaint_reason: str) -> Ticket:
        ticket_id = self._generate_ticket_id(state)

        priority = state.risk_level
        if priority == RiskLevel.LOW:
            priority = RiskLevel.MEDIUM

        return Ticket(
            ticket_id=ticket_id,
            customer_id=state.customer.customer_id if state.customer else None,
            session_id=state.session_id,
            category=TicketCategory.COMPLAINT,
            priority=priority,
            summary=complaint_reason,
            assigned_team="customer_support",
        )

    def _generate_ticket_id(self, state: CallState) -> str:
        short_session = state.session_id.split("-")[0].upper()
        return f"COMP-{short_session}"