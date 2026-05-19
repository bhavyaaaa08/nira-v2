from __future__ import annotations

import re

from app.core.enums import ComplianceStatus
from app.core.schemas import AgentResponse, ComplianceResult, JudgeResult
from app.core.state import CallState


class ResponseJudgeAgent:
    """
    Final response quality judge for NIRA.

    It checks:
    - Is the response short enough for voice?
    - Does it repeat the previous response?
    - Did compliance require a safe rewrite?
    - Is the response empty?
    - Does it end with a useful next step?
    """

    def judge(
        self,
        response_text: str,
        state: CallState,
        compliance_result: ComplianceResult | None = None,
    ) -> JudgeResult:
        response = (response_text or "").strip()
        issues: list[str] = []

        if not response:
            issues.append("empty_response")
            return JudgeResult(
                approved=False,
                score=0,
                issues=issues,
                final_response="I am sorry, I could not process that. Could you please repeat?",
            )

        if compliance_result and compliance_result.status != ComplianceStatus.PASSED:
            issues.append("compliance_rewrite_required")
            safe_response = compliance_result.safe_response or (
                "I need to handle this safely. Let me route it to the right team."
            )
            return JudgeResult(
                approved=True,
                score=7,
                issues=issues,
                final_response=self._make_voice_safe(safe_response),
            )

        if self._is_too_long(response):
            issues.append("too_long_for_voice")

        if self._repeats_previous_response(response, state):
            issues.append("repeats_previous_response")

        if not self._has_next_step(response):
            issues.append("missing_clear_next_step")

        final_response = self._make_voice_safe(response)

        score = self._score_from_issues(issues)
        approved = score >= 6

        if not approved:
            final_response = self._fallback_response(state)

        return JudgeResult(
            approved=approved,
            score=score,
            issues=issues,
            final_response=final_response,
        )

    def finalize(
        self,
        response: AgentResponse,
        state: CallState,
        compliance_result: ComplianceResult | None = None,
    ) -> AgentResponse:
        judge_result = self.judge(
            response_text=response.response_text,
            state=state,
            compliance_result=compliance_result,
        )

        response.response_text = judge_result.final_response
        response.metadata["judge_result"] = judge_result.model_dump()

        if judge_result.issues:
            response.actions.append("response_judge_reviewed")

        return response

    def _is_too_long(self, response: str) -> bool:
        words = response.split()
        sentence_count = len(re.findall(r"[.!?]+", response))

        return len(words) > 45 or sentence_count > 3

    def _repeats_previous_response(self, response: str, state: CallState) -> bool:
        if not state.last_agent_response:
            return False

        current = self._normalize(response)
        previous = self._normalize(state.last_agent_response)

        if not current or not previous:
            return False

        if current == previous:
            return True

        overlap = len(set(current.split()) & set(previous.split()))
        total = max(len(set(current.split())), 1)

        return (overlap / total) > 0.85

    def _has_next_step(self, response: str) -> bool:
        lower_response = response.lower()

        next_step_markers = [
            "?",
            "could you",
            "please",
            "i can",
            "i will",
            "i have",
            "you can",
            "would you like",
            "share",
            "confirm",
            "review",
            "ticket",
            "connect",
            "raise",
            "pay",
            "verify",
        ]

        return any(marker in lower_response for marker in next_step_markers)

    def _make_voice_safe(self, response: str) -> str:
        cleaned = response.strip()
        cleaned = re.sub(r"\s+", " ", cleaned)

        sentences = re.split(r"(?<=[.!?])\s+", cleaned)

        if len(sentences) > 3:
            cleaned = " ".join(sentences[:3])

        words = cleaned.split()
        if len(words) > 55:
            cleaned = " ".join(words[:55]).rstrip(",") + "."

        return cleaned

    def _score_from_issues(self, issues: list[str]) -> int:
        score = 10

        penalty_map = {
            "too_long_for_voice": 2,
            "repeats_previous_response": 3,
            "missing_clear_next_step": 1,
            "empty_response": 10,
            "compliance_rewrite_required": 3,
        }

        for issue in issues:
            score -= penalty_map.get(issue, 1)

        return max(0, score)

    def _fallback_response(self, state: CallState) -> str:
        if not state.identity_verified:
            return "For security, could you please confirm your identity first?"

        return (
            "I understand. Let me keep this simple and route the request to the right team."
        )

    def _normalize(self, text: str) -> str:
        lowered = text.lower()
        lowered = re.sub(r"[^\w\s]", "", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered