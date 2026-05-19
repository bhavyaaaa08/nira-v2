from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.core.enums import (
    AgentName,
    CallPhase,
    ComplianceStatus,
    IdentityStatus,
    Intent,
    Language,
    PaymentStatus,
    RiskLevel,
    TicketCategory,
    TicketStatus,
)


class CustomerProfile(BaseModel):
    customer_id: Optional[int] = None
    name: str
    phone: str
    preferred_language: Language = Language.ENGLISH
    is_verified: bool = False


class LoanAccount(BaseModel):
    loan_id: Optional[int] = None
    customer_id: Optional[int] = None
    loan_amount: float
    due_date: str
    overdue_days: int = 0
    status: str = "active"
    late_fee: Optional[float] = None

class IdentityResult(BaseModel):
    status: IdentityStatus = IdentityStatus.UNCERTAIN
    verified: bool = False
    confidence: float = 0.0
    reason: str = ""
    safe_reply: str = ""
    matched_name: Optional[str] = None

class ExtractedEntities(BaseModel):
    amount: Optional[float] = None
    date: Optional[str] = None
    time: Optional[str] = None
    transaction_id: Optional[str] = None
    payment_method: Optional[str] = None
    complaint_reason: Optional[str] = None
    dispute_reason: Optional[str] = None
    kyc_field: Optional[str] = None
    language_hint: Optional[Language] = None
    raw_entities: Dict[str, Any] = Field(default_factory=dict)


class IntentResult(BaseModel):
    intent: Intent = Intent.UNKNOWN
    confidence: float = 0.0
    entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    source: str = "rule_based"


class RiskResult(BaseModel):
    score: int = Field(default=0, ge=0, le=100)
    level: RiskLevel = RiskLevel.LOW
    reasons: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None


class ComplianceResult(BaseModel):
    status: ComplianceStatus = ComplianceStatus.PASSED
    violations: List[str] = Field(default_factory=list)
    safe_response: Optional[str] = None


class JudgeResult(BaseModel):
    approved: bool = True
    score: int = Field(default=10, ge=0, le=10)
    issues: List[str] = Field(default_factory=list)
    final_response: str


class AgentDecision(BaseModel):
    selected_agent: AgentName
    reason: str
    intent: Intent
    risk_level: RiskLevel = RiskLevel.LOW


class TurnInput(BaseModel):
    session_id: str
    user_text: str
    channel: str = "text"
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentResponse(BaseModel):
    agent_name: AgentName
    response_text: str
    next_phase: Optional[CallPhase] = None
    outcome: Optional[str] = None
    actions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TurnResult(BaseModel):
    session_id: str
    user_text: str
    intent_result: IntentResult
    risk_result: RiskResult
    agent_decision: AgentDecision
    compliance_result: ComplianceResult
    judge_result: JudgeResult
    final_response: str
    actions: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class PaymentVerification(BaseModel):
    transaction_id: str
    amount: Optional[float] = None
    status: PaymentStatus = PaymentStatus.VERIFICATION_PENDING
    notes: Optional[str] = None


class Ticket(BaseModel):
    ticket_id: str
    customer_id: Optional[int] = None
    session_id: Optional[str] = None
    category: TicketCategory
    status: TicketStatus = TicketStatus.OPEN
    priority: RiskLevel = RiskLevel.MEDIUM
    summary: str
    assigned_team: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)