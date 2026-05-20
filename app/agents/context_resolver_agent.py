from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.core.enums import AgentName, Intent, PendingAction
from app.core.schemas import IntentResult
from app.core.state import CallState


@dataclass
class ContextResolution:
    agent_name: AgentName = AgentName.CONTEXT_RESOLVER
    resolved: bool = False
    original_intent: Intent = Intent.UNKNOWN
    resolved_intent: Intent = Intent.UNKNOWN
    pending_action: Optional[PendingAction] = None
    confidence: float = 0.0
    reason: str = ""


class ContextResolverAgent:
    """
    Resolves vague follow-up replies using CallState memory.

    Example:
    Assistant: Would you like me to raise an extension review request?
    User: yes
    Rule-based intent: GENERAL
    Context resolver: CONFIRM_PENDING_ACTION + pending_action=CONFIRM_EXTENSION_REVIEW

    This is deterministic now. Later, the fuzzy yes/no classification can be
    upgraded with Gemini/Groq while keeping final action execution deterministic.
    """

    def resolve(
        self,
        state: CallState,
        intent_result: IntentResult,
    ) -> ContextResolution:
        original_intent = intent_result.intent

        if not state.pending_action:
            return ContextResolution(
                resolved=False,
                original_intent=original_intent,
                resolved_intent=original_intent,
                reason="No pending action exists.",
            )

        user_text = state.last_user_text or ""

        if not self._should_try_context_resolution(user_text, original_intent):
            return ContextResolution(
                resolved=False,
                original_intent=original_intent,
                resolved_intent=original_intent,
                pending_action=state.pending_action,
                reason="Current turn has a clear non-contextual intent.",
            )

        if self._is_affirmative(user_text):
            intent_result.intent = Intent.CONFIRM_PENDING_ACTION
            intent_result.confidence = 0.92
            intent_result.source = "context_resolver"
            intent_result.entities.raw_entities["context_resolution"] = {
                "resolved": True,
                "pending_action": state.pending_action.value,
                "resolution": "confirmed",
            }

            return ContextResolution(
                resolved=True,
                original_intent=original_intent,
                resolved_intent=Intent.CONFIRM_PENDING_ACTION,
                pending_action=state.pending_action,
                confidence=0.92,
                reason="User confirmed the pending action.",
            )

        if self._is_negative(user_text):
            intent_result.intent = Intent.CANCEL_PENDING_ACTION
            intent_result.confidence = 0.9
            intent_result.source = "context_resolver"
            intent_result.entities.raw_entities["context_resolution"] = {
                "resolved": True,
                "pending_action": state.pending_action.value,
                "resolution": "cancelled",
            }

            return ContextResolution(
                resolved=True,
                original_intent=original_intent,
                resolved_intent=Intent.CANCEL_PENDING_ACTION,
                pending_action=state.pending_action,
                confidence=0.9,
                reason="User declined the pending action.",
            )

        return ContextResolution(
            resolved=False,
            original_intent=original_intent,
            resolved_intent=original_intent,
            pending_action=state.pending_action,
            reason="Pending action exists, but user reply was not a clear confirmation or rejection.",
        )

    def _should_try_context_resolution(self, user_text: str, intent: Intent) -> bool:
        normalized = self._normalize(user_text)

        if intent in {Intent.GENERAL, Intent.UNKNOWN}:
            return True

        # Short replies are often contextual even if a rule misclassifies later.
        if len(normalized.split()) <= 5:
            return True

        return False

    def _is_affirmative(self, text: str) -> bool:
        normalized = self._normalize(text)

        affirmative_phrases = [
            "yes",
            "yeah",
            "yep",
            "yup",
            "ok",
            "okay",
            "sure",
            "please",
            "please do",
            "do it",
            "do that",
            "go ahead",
            "raise it",
            "raise request",
            "please raise",
            "please raise it",
            "you can do it",
            "haan",
            "ha",
            "ji",
            "theek hai",
            "kar do",
            "haan kar do",
            "please kar do",
            "kardo",
        ]

        exact_affirmatives = {
            "yes",
            "yeah",
            "yep",
            "yup",
            "ok",
            "okay",
            "sure",
            "haan",
            "ha",
            "ji",
        }

        if normalized in exact_affirmatives:
            return True

        return any(phrase in normalized for phrase in affirmative_phrases)

    def _is_negative(self, text: str) -> bool:
        normalized = self._normalize(text)

        negative_phrases = [
            "no",
            "nope",
            "not now",
            "don't",
            "dont",
            "do not",
            "leave it",
            "cancel",
            "no need",
            "not required",
            "nahi",
            "mat karo",
            "rehne do",
        ]

        exact_negatives = {
            "no",
            "nope",
            "nahi",
        }

        if normalized in exact_negatives:
            return True

        return any(phrase in normalized for phrase in negative_phrases)

    def _normalize(self, text: str) -> str:
        normalized = (text or "").lower().strip()
        normalized = normalized.replace("हाँ", " haan ")
        normalized = normalized.replace("हां", " haan ")
        normalized = normalized.replace("जी", " ji ")
        normalized = normalized.replace("नहीं", " nahi ")
        normalized = normalized.replace("नही", " nahi ")
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized