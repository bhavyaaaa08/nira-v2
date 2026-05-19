from __future__ import annotations

from app.core.enums import AgentName, CallPhase, RiskLevel, TicketCategory
from app.core.schemas import AgentResponse, IntentResult, Ticket
from app.core.state import CallState


class KYCAgent:
    """
    Handles KYC-related customer requests:
    - mobile number update
    - address update
    - Aadhaar/PAN update
    - name correction
    - general KYC support

    This is demo-safe. It does not perform real KYC updates.
    It only raises a review request.
    """

    def respond(self, state: CallState, intent_result: IntentResult) -> AgentResponse:
        state.mark_kyc_request()
        state.advance_to(CallPhase.KYC)

        kyc_field = intent_result.entities.kyc_field or "kyc_details"
        ticket = self.create_ticket(state, kyc_field)

        readable_field = self._readable_field(kyc_field)

        return AgentResponse(
            agent_name=AgentName.KYC,
            response_text=(
                f"I can raise a KYC update request for your {readable_field}. "
                f"For security, an executive will verify it before any change is made. "
                f"Your request ticket ID is {ticket.ticket_id}."
            ),
            next_phase=CallPhase.KYC,
            outcome="kyc_update_requested",
            actions=[
                "create_kyc_ticket",
                "route_to_kyc_team",
                "require_human_verification",
            ],
            metadata={
                "ticket": ticket.model_dump(),
                "kyc_field": kyc_field,
            },
        )

    def create_ticket(self, state: CallState, kyc_field: str) -> Ticket:
        ticket_id = self._generate_ticket_id(state)

        return Ticket(
            ticket_id=ticket_id,
            customer_id=state.customer.customer_id if state.customer else None,
            session_id=state.session_id,
            category=TicketCategory.KYC,
            priority=RiskLevel.MEDIUM,
            summary=f"KYC update requested for {kyc_field}.",
            assigned_team="kyc_operations_team",
        )

    def _readable_field(self, field_name: str) -> str:
        return field_name.replace("_", " ")

    def _generate_ticket_id(self, state: CallState) -> str:
        short_session = state.session_id.split("-")[0].upper()
        return f"KYC-{short_session}"