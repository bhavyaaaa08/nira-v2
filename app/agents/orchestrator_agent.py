from __future__ import annotations

from app.agents.compliance_agent import ComplianceAgent
from app.agents.complaint_agent import ComplaintAgent
from app.agents.fraud_dispute_agent import FraudDisputeAgent
from app.agents.identity_agent import IdentityAgent
from app.agents.intent_entity_agent import IntentEntityAgent
from app.agents.kyc_agent import KYCAgent
from app.agents.loan_servicing_agent import LoanServicingAgent
from app.agents.payment_operations_agent import PaymentOperationsAgent
from app.agents.response_judge_agent import ResponseJudgeAgent
from app.agents.risk_scoring_agent import RiskScoringAgent
from app.core.enums import (
    AgentName,
    CallPhase,
    ComplianceStatus,
    IdentityStatus,
    Intent,
    RiskLevel,
)
from app.core.schemas import (
    AgentDecision,
    AgentResponse,
    ComplianceResult,
    IntentResult,
    JudgeResult,
    RiskResult,
    TurnResult,
)
from app.core.state import CallState


class OrchestratorAgent:
    """
    Central multi-agent coordinator for NIRA.

    Pipeline:
    1. Add user turn to state
    2. Verify identity if needed
    3. Detect intent and entities
    4. Score risk
    5. Route to specialist agent
    6. Run compliance check
    7. Run response judge
    8. Save decision trace
    9. Return final response
    """

    def __init__(self) -> None:
        self.identity_agent = IdentityAgent()
        self.intent_agent = IntentEntityAgent()
        self.risk_agent = RiskScoringAgent()

        self.loan_servicing_agent = LoanServicingAgent()
        self.payment_operations_agent = PaymentOperationsAgent()
        self.kyc_agent = KYCAgent()
        self.fraud_dispute_agent = FraudDisputeAgent()
        self.complaint_agent = ComplaintAgent()

        self.compliance_agent = ComplianceAgent()
        self.response_judge_agent = ResponseJudgeAgent()

    def process_turn(
        self,
        state: CallState,
        user_text: str,
        channel: str = "text",
    ) -> TurnResult:
        state.add_turn(
            role="user",
            content=user_text,
            metadata={"channel": channel},
        )

        if not state.identity_verified:
            return self._handle_identity_turn(state, user_text)

        intent_result = self.intent_agent.analyze(user_text)
        state.last_intent = intent_result.intent

        risk_result = self.risk_agent.analyze(
            state=state,
            intent_result=intent_result,
            user_text=user_text,
        )

        agent_decision = self._decide_agent(
            intent_result=intent_result,
            risk_result=risk_result,
            state=state,
        )

        raw_response = self._call_selected_agent(
            state=state,
            intent_result=intent_result,
            decision=agent_decision,
        )

        return self._finalize_turn(
            state=state,
            user_text=user_text,
            intent_result=intent_result,
            risk_result=risk_result,
            agent_decision=agent_decision,
            raw_response=raw_response,
        )

    def _handle_identity_turn(
        self,
        state: CallState,
        user_text: str,
    ) -> TurnResult:
        expected_name = state.customer.name if state.customer else "the account holder"

        identity_result = self.identity_agent.verify(
            user_text=user_text,
            expected_customer_name=expected_name,
            state=state,
        )

        if identity_result.status == IdentityStatus.VERIFIED:
            intent_result = IntentResult(
                intent=Intent.IDENTITY_CONFIRMATION,
                confidence=identity_result.confidence,
                source="identity_agent",
            )

            risk_result = RiskResult(
                score=state.risk_score,
                level=state.risk_level,
                reasons=["Identity verified."],
                recommended_action="Deliver account briefing.",
            )

            agent_decision = AgentDecision(
                selected_agent=AgentName.LOAN_SERVICING,
                reason="Identity verified, so account briefing should be delivered.",
                intent=Intent.IDENTITY_CONFIRMATION,
                risk_level=state.risk_level,
            )

            raw_response = self.loan_servicing_agent.initial_briefing(state)

            return self._finalize_turn(
                state=state,
                user_text=user_text,
                intent_result=intent_result,
                risk_result=risk_result,
                agent_decision=agent_decision,
                raw_response=raw_response,
            )

        if identity_result.status == IdentityStatus.WRONG_NUMBER:
            state.close(outcome="wrong_number")

        if identity_result.status == IdentityStatus.MAX_ATTEMPTS_EXCEEDED:
            state.close(outcome="identity_failed")

        intent_result = IntentResult(
            intent=Intent.WRONG_NUMBER
            if identity_result.status == IdentityStatus.WRONG_NUMBER
            else Intent.UNKNOWN,
            confidence=identity_result.confidence,
            source="identity_agent",
        )

        risk_result = RiskResult(
            score=state.risk_score,
            level=state.risk_level,
            reasons=[identity_result.reason],
            recommended_action="Do not reveal account details.",
        )

        agent_decision = AgentDecision(
            selected_agent=AgentName.IDENTITY,
            reason=identity_result.reason,
            intent=intent_result.intent,
            risk_level=state.risk_level,
        )

        raw_response = AgentResponse(
            agent_name=AgentName.IDENTITY,
            response_text=identity_result.safe_reply,
            next_phase=state.phase,
            outcome=state.outcome,
            actions=["identity_verification"],
            metadata={"identity_result": identity_result.model_dump()},
        )

        return self._finalize_turn(
            state=state,
            user_text=user_text,
            intent_result=intent_result,
            risk_result=risk_result,
            agent_decision=agent_decision,
            raw_response=raw_response,
        )

    def _decide_agent(
        self,
        intent_result: IntentResult,
        risk_result: RiskResult,
        state: CallState,
    ) -> AgentDecision:
        intent = intent_result.intent

        if intent in {Intent.PAYMENT_DONE, Intent.PAYMENT_METHOD}:
            return AgentDecision(
                selected_agent=AgentName.PAYMENT_OPERATIONS,
                reason="Payment-related intent detected.",
                intent=intent,
                risk_level=risk_result.level,
            )

        if intent == Intent.KYC_UPDATE:
            return AgentDecision(
                selected_agent=AgentName.KYC,
                reason="KYC update intent detected.",
                intent=intent,
                risk_level=risk_result.level,
            )

        if intent in {Intent.FRAUD_CLAIM, Intent.DISPUTE}:
            return AgentDecision(
                selected_agent=AgentName.FRAUD_DISPUTE,
                reason="Fraud or dispute intent detected.",
                intent=intent,
                risk_level=risk_result.level,
            )

        if intent == Intent.COMPLAINT:
            return AgentDecision(
                selected_agent=AgentName.COMPLAINT,
                reason="Complaint intent detected.",
                intent=intent,
                risk_level=risk_result.level,
            )

        if intent == Intent.ESCALATION_REQUEST:
            return AgentDecision(
                selected_agent=AgentName.ORCHESTRATOR,
                reason="Customer requested human escalation.",
                intent=intent,
                risk_level=risk_result.level,
            )

        return AgentDecision(
            selected_agent=AgentName.LOAN_SERVICING,
            reason="Default route for loan servicing conversation.",
            intent=intent,
            risk_level=risk_result.level,
        )

    def _call_selected_agent(
        self,
        state: CallState,
        intent_result: IntentResult,
        decision: AgentDecision,
    ) -> AgentResponse:
        selected_agent = decision.selected_agent

        if selected_agent == AgentName.PAYMENT_OPERATIONS:
            return self.payment_operations_agent.respond(state, intent_result)

        if selected_agent == AgentName.KYC:
            return self.kyc_agent.respond(state, intent_result)

        if selected_agent == AgentName.FRAUD_DISPUTE:
            return self.fraud_dispute_agent.respond(state, intent_result)

        if selected_agent == AgentName.COMPLAINT:
            return self.complaint_agent.respond(state, intent_result)

        if selected_agent == AgentName.ORCHESTRATOR:
            state.mark_escalation()
            return AgentResponse(
                agent_name=AgentName.ORCHESTRATOR,
                response_text=(
                    "I understand. I can connect this to a human executive for review. "
                    "I have marked this call for escalation."
                ),
                next_phase=CallPhase.ESCALATION,
                outcome="escalated",
                actions=["human_escalation_requested"],
            )

        return self.loan_servicing_agent.respond(state, intent_result)

    def _finalize_turn(
        self,
        state: CallState,
        user_text: str,
        intent_result: IntentResult,
        risk_result: RiskResult,
        agent_decision: AgentDecision,
        raw_response: AgentResponse,
    ) -> TurnResult:
        compliance_result = self.compliance_agent.check(
            response_text=raw_response.response_text,
            state=state,
        )

        judge_result = self.response_judge_agent.judge(
            response_text=raw_response.response_text,
            state=state,
            compliance_result=compliance_result,
        )

        final_response = judge_result.final_response

        actions = list(raw_response.actions)

        if compliance_result.status != ComplianceStatus.PASSED:
            actions.append("compliance_rewrite_applied")

        if judge_result.issues:
            actions.append("response_judge_reviewed")

        state.add_turn(
            role="assistant",
            content=final_response,
            metadata={
                "agent": agent_decision.selected_agent.value,
                "intent": intent_result.intent.value,
                "risk_score": risk_result.score,
                "risk_level": risk_result.level.value,
                "actions": actions,
            },
        )

        state.add_decision_trace(
            {
                "user_text": user_text,
                "detected_intent": intent_result.intent.value,
                "entities": intent_result.entities.model_dump(),
                "selected_agent": agent_decision.selected_agent.value,
                "agent_reason": agent_decision.reason,
                "risk_score": risk_result.score,
                "risk_level": risk_result.level.value,
                "risk_reasons": risk_result.reasons,
                "compliance_status": compliance_result.status.value,
                "compliance_violations": compliance_result.violations,
                "judge_score": judge_result.score,
                "judge_issues": judge_result.issues,
                "final_response": final_response,
                "actions": actions,
            }
        )

        return TurnResult(
            session_id=state.session_id,
            user_text=user_text,
            intent_result=intent_result,
            risk_result=risk_result,
            agent_decision=agent_decision,
            compliance_result=compliance_result,
            judge_result=judge_result,
            final_response=final_response,
            actions=actions,
        )