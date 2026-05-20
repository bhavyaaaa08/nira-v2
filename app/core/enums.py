from enum import Enum


class CallPhase(str, Enum):
    PRE_CALL = "pre_call"
    GREETING = "greeting"
    IDENTITY_VERIFICATION = "identity_verification"
    ACCOUNT_BRIEFING = "account_briefing"
    SERVICING = "servicing"
    PAYMENT = "payment"
    KYC = "kyc"
    DISPUTE = "dispute"
    COMPLAINT = "complaint"
    ESCALATION = "escalation"
    CLOSING = "closing"
    POST_CALL = "post_call"


class AgentName(str, Enum):
    ORCHESTRATOR = "orchestrator_agent"
    IDENTITY = "identity_agent"
    INTENT_ENTITY = "intent_entity_agent"
    CONTEXT_RESOLVER = "context_resolver_agent"
    LOAN_SERVICING = "loan_servicing_agent"
    PAYMENT_OPERATIONS = "payment_operations_agent"
    KYC = "kyc_agent"
    FRAUD_DISPUTE = "fraud_dispute_agent"
    COMPLAINT = "complaint_agent"
    RISK_SCORING = "risk_scoring_agent"
    COMPLIANCE = "compliance_agent"
    RESPONSE_JUDGE = "response_judge_agent"
    SUMMARY = "summary_agent"
    AUTOMATION = "automation_agent"
    

class IdentityStatus(str, Enum):
    VERIFIED = "verified"
    WRONG_NUMBER = "wrong_number"
    UNCERTAIN = "uncertain"
    MAX_ATTEMPTS_EXCEEDED = "max_attempts_exceeded"

class Intent(str, Enum):
    IDENTITY_CONFIRMATION = "identity_confirmation"
    WRONG_NUMBER = "wrong_number"

    PROMISE_TO_PAY = "promise_to_pay"
    PAYMENT_DONE = "payment_done"
    PAYMENT_METHOD = "payment_method"
    PARTIAL_PAYMENT = "partial_payment"
    CANNOT_PAY = "cannot_pay"
    NEEDS_EXTENSION = "needs_extension"

    PENALTY_QUESTION = "penalty_question"
    WAIVER_REQUEST = "waiver_request"

    KYC_UPDATE = "kyc_update"
    FRAUD_CLAIM = "fraud_claim"
    DISPUTE = "dispute"
    COMPLAINT = "complaint"

    ESCALATION_REQUEST = "escalation_request"
    CLOSING = "closing"
    CONFIRM_PENDING_ACTION = "confirm_pending_action"
    CANCEL_PENDING_ACTION = "cancel_pending_action"
    GENERAL = "general"
    UNKNOWN = "unknown"


class PendingAction(str, Enum):
    CONFIRM_WAIVER_REVIEW = "confirm_waiver_review"
    CONFIRM_EXTENSION_REVIEW = "confirm_extension_review"
    CONFIRM_ESCALATION = "confirm_escalation"
    CONFIRM_KYC_UPDATE = "confirm_kyc_update"
    CONFIRM_DISPUTE_REVIEW = "confirm_dispute_review"
    CONFIRM_COMPLAINT_REGISTRATION = "confirm_complaint_registration"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceStatus(str, Enum):
    PASSED = "passed"
    BLOCKED = "blocked"
    NEEDS_REWRITE = "needs_rewrite"


class PaymentStatus(str, Enum):
    NOT_INITIATED = "not_initiated"
    PROMISED = "promised"
    VERIFICATION_PENDING = "verification_pending"
    VERIFIED = "verified"
    FAILED = "failed"
    AMOUNT_MISMATCH = "amount_mismatch"
    TRANSACTION_NOT_FOUND = "transaction_not_found"


class TicketCategory(str, Enum):
    COMPLAINT = "complaint"
    DISPUTE = "dispute"
    FRAUD = "fraud"
    KYC = "kyc"
    PAYMENT = "payment"
    ESCALATION = "escalation"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Language(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hinglish"
    TAMIL = "ta"
    UNKNOWN = "unknown"