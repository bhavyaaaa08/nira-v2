from __future__ import annotations

from app.core.enums import AgentName, CallPhase, PaymentStatus
from app.core.schemas import AgentResponse, IntentResult, PaymentVerification
from app.core.state import CallState


class PaymentOperationsAgent:
    """
    Handles payment operations:
    - already-paid claims
    - transaction ID collection
    - simulated payment verification
    - payment method guidance
    - amount mismatch cases
    """

    def respond(self, state: CallState, intent_result: IntentResult) -> AgentResponse:
        entities = intent_result.entities

        if entities.transaction_id:
            verification = self.verify_payment(
                transaction_id=entities.transaction_id,
                expected_amount=state.loan.loan_amount if state.loan else None,
                provided_amount=entities.amount,
            )
            return self._handle_verification_result(state, verification)

        state.mark_payment_verification_pending()

        return AgentResponse(
            agent_name=AgentName.PAYMENT_OPERATIONS,
            response_text=(
                "Thank you for letting me know. Could you share the transaction reference number "
                "or UTR so I can flag it for payment verification?"
            ),
            next_phase=CallPhase.PAYMENT,
            outcome="payment_verification_pending",
            actions=["request_transaction_reference"],
        )

    def payment_methods(self) -> AgentResponse:
        return AgentResponse(
            agent_name=AgentName.PAYMENT_OPERATIONS,
            response_text=(
                "You can pay using UPI, bank transfer, the loan app, or the lender payment portal. "
                "Please keep the transaction reference after payment."
            ),
            next_phase=CallPhase.PAYMENT,
            actions=["share_payment_methods"],
        )

    def verify_payment(
        self,
        transaction_id: str,
        expected_amount: float | None = None,
        provided_amount: float | None = None,
    ) -> PaymentVerification:
        cleaned_txn = transaction_id.strip().upper()

        if provided_amount is not None and expected_amount is not None:
            if abs(provided_amount - expected_amount) > 1:
                return PaymentVerification(
                    transaction_id=cleaned_txn,
                    amount=provided_amount,
                    status=PaymentStatus.AMOUNT_MISMATCH,
                    notes="Provided amount does not match expected loan amount.",
                )

        if cleaned_txn.startswith("FAIL"):
            return PaymentVerification(
                transaction_id=cleaned_txn,
                amount=provided_amount,
                status=PaymentStatus.FAILED,
                notes="Payment appears failed in simulator.",
            )

        if cleaned_txn.startswith("MISS"):
            return PaymentVerification(
                transaction_id=cleaned_txn,
                amount=provided_amount,
                status=PaymentStatus.TRANSACTION_NOT_FOUND,
                notes="Transaction was not found in simulator.",
            )

        if cleaned_txn.startswith("OK") or cleaned_txn.endswith("123"):
            return PaymentVerification(
                transaction_id=cleaned_txn,
                amount=provided_amount,
                status=PaymentStatus.VERIFIED,
                notes="Payment verified in simulator.",
            )

        return PaymentVerification(
            transaction_id=cleaned_txn,
            amount=provided_amount,
            status=PaymentStatus.VERIFICATION_PENDING,
            notes="Payment verification is pending.",
        )

    def _handle_verification_result(
        self,
        state: CallState,
        verification: PaymentVerification,
    ) -> AgentResponse:
        state.payment_status = verification.status

        if verification.status == PaymentStatus.VERIFIED:
            state.outcome = "payment_verified"
            state.outcome_detail = verification.transaction_id

            return AgentResponse(
                agent_name=AgentName.PAYMENT_OPERATIONS,
                response_text=(
                    "Thank you. I have verified the payment reference in our simulator and "
                    "marked this for account update."
                ),
                next_phase=CallPhase.CLOSING,
                outcome="payment_verified",
                actions=["mark_payment_verified", "update_payment_status"],
                metadata={"verification": verification.model_dump()},
            )

        if verification.status == PaymentStatus.AMOUNT_MISMATCH:
            state.outcome = "payment_amount_mismatch"
            state.outcome_detail = verification.transaction_id

            return AgentResponse(
                agent_name=AgentName.PAYMENT_OPERATIONS,
                response_text=(
                    "Thank you. The payment reference was received, but the amount does not match "
                    "the due amount, so I will raise it for manual review."
                ),
                next_phase=CallPhase.ESCALATION,
                outcome="payment_amount_mismatch",
                actions=["raise_payment_review_ticket"],
                metadata={"verification": verification.model_dump()},
            )

        if verification.status == PaymentStatus.FAILED:
            state.outcome = "payment_failed"
            state.outcome_detail = verification.transaction_id

            return AgentResponse(
                agent_name=AgentName.PAYMENT_OPERATIONS,
                response_text=(
                    "I checked the reference, and it appears the payment may have failed. "
                    "Please retry the payment or share another reference if available."
                ),
                next_phase=CallPhase.PAYMENT,
                outcome="payment_failed",
                actions=["request_payment_retry"],
                metadata={"verification": verification.model_dump()},
            )

        if verification.status == PaymentStatus.TRANSACTION_NOT_FOUND:
            state.outcome = "transaction_not_found"
            state.outcome_detail = verification.transaction_id

            return AgentResponse(
                agent_name=AgentName.PAYMENT_OPERATIONS,
                response_text=(
                    "I could not find this transaction reference in the simulator. "
                    "Please recheck the reference number or share the UTR."
                ),
                next_phase=CallPhase.PAYMENT,
                outcome="transaction_not_found",
                actions=["request_correct_transaction_reference"],
                metadata={"verification": verification.model_dump()},
            )

        state.mark_payment_verification_pending(verification.transaction_id)

        return AgentResponse(
            agent_name=AgentName.PAYMENT_OPERATIONS,
            response_text=(
                "Thank you. I have received the transaction reference and marked it for verification. "
                "It may take some time to reflect in the account."
            ),
            next_phase=CallPhase.PAYMENT,
            outcome="payment_verification_pending",
            actions=["mark_payment_verification_pending"],
            metadata={"verification": verification.model_dump()},
        )