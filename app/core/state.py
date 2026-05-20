from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

from app.core.enums import CallPhase, Intent, Language, PaymentStatus, PendingAction, RiskLevel
from app.core.schemas import CustomerProfile, LoanAccount


@dataclass
class ConversationTurn:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CallState:
    session_id: str = field(default_factory=lambda: str(uuid4()))
    phase: CallPhase = CallPhase.PRE_CALL

    customer: Optional[CustomerProfile] = None
    loan: Optional[LoanAccount] = None

    language: Language = Language.ENGLISH
    identity_verified: bool = False
    identity_attempts: int = 0

    turn_number: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None

    last_intent: Intent = Intent.UNKNOWN
    last_user_text: Optional[str] = None
    last_agent_response: Optional[str] = None

    risk_score: int = 0
    risk_level: RiskLevel = RiskLevel.LOW
    frustration_score: float = 0.0

    payment_status: PaymentStatus = PaymentStatus.NOT_INITIATED
    commitment_received: bool = False
    commitment_time: Optional[str] = None
    commitment_amount: Optional[float] = None

    complaint_registered: bool = False
    dispute_registered: bool = False
    kyc_request_registered: bool = False
    escalation_required: bool = False
    escalation_offered: bool = False

    outcome: Optional[str] = None
    outcome_detail: Optional[str] = None

    pending_action: Optional[PendingAction] = None
    pending_action_data: Dict[str, Any] = field(default_factory=dict)

    conversation: List[ConversationTurn] = field(default_factory=list)
    decision_trace: List[Dict[str, Any]] = field(default_factory=list)

    def advance_to(self, phase: CallPhase) -> None:
        self.phase = phase

    def set_pending_action(
        self,
        action: PendingAction,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.pending_action = action
        self.pending_action_data = data or {}

    def clear_pending_action(self) -> None:
        self.pending_action = None
        self.pending_action_data = {}

    def add_turn(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.conversation.append(
            ConversationTurn(
                role=role,
                content=content,
                metadata=metadata or {},
            )
        )

        if role == "user":
            self.turn_number += 1
            self.last_user_text = content

        if role == "assistant":
            self.last_agent_response = content

    def mark_identity_verified(self) -> None:
        self.identity_verified = True
        if self.customer:
            self.customer.is_verified = True
        self.advance_to(CallPhase.ACCOUNT_BRIEFING)

    def mark_commitment(
        self,
        time_text: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> None:
        self.commitment_received = True
        self.commitment_time = time_text
        self.commitment_amount = amount
        self.payment_status = PaymentStatus.PROMISED
        self.outcome = "promise_to_pay"
        self.outcome_detail = time_text or "payment commitment received"

    def mark_payment_verification_pending(self, transaction_id: Optional[str] = None) -> None:
        self.payment_status = PaymentStatus.VERIFICATION_PENDING
        self.outcome = "payment_verification_pending"
        self.outcome_detail = transaction_id

    def mark_complaint(self) -> None:
        self.complaint_registered = True
        self.outcome = "complaint_registered"

    def mark_dispute(self) -> None:
        self.dispute_registered = True
        self.outcome = "dispute_registered"

    def mark_kyc_request(self) -> None:
        self.kyc_request_registered = True
        self.outcome = "kyc_update_requested"

    def mark_escalation(self) -> None:
        self.escalation_required = True
        self.escalation_offered = True
        self.advance_to(CallPhase.ESCALATION)
        self.outcome = "escalated"

    def close(self, outcome: Optional[str] = None) -> None:
        self.ended_at = datetime.now()
        self.phase = CallPhase.POST_CALL
        if outcome:
            self.outcome = outcome

    def add_decision_trace(self, trace: Dict[str, Any]) -> None:
        self.decision_trace.append(
            {
                "turn_number": self.turn_number,
                "timestamp": datetime.now().isoformat(),
                **trace,
            }
        )

    @property
    def duration_seconds(self) -> int:
        end_time = self.ended_at or datetime.now()
        return int((end_time - self.started_at).total_seconds())

    def recent_history(self, limit: int = 8) -> List[ConversationTurn]:
        return self.conversation[-limit:]

    def context_summary(self) -> str:
        customer_name = self.customer.name if self.customer else "unknown"
        loan_amount = self.loan.loan_amount if self.loan else "unknown"
        overdue_days = self.loan.overdue_days if self.loan else "unknown"

        return (
            f"Session: {self.session_id}\n"
            f"Phase: {self.phase.value}\n"
            f"Customer: {customer_name}\n"
            f"Identity verified: {self.identity_verified}\n"
            f"Loan amount: {loan_amount}\n"
            f"Overdue days: {overdue_days}\n"
            f"Last intent: {self.last_intent.value}\n"
            f"Risk: {self.risk_level.value} ({self.risk_score}/100)\n"
            f"Payment status: {self.payment_status.value}\n"
            f"Outcome: {self.outcome or 'not_decided'}"
            f"Pending action: {self.pending_action.value if self.pending_action else 'none'}"

        )