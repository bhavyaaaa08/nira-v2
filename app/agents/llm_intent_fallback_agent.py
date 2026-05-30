from __future__ import annotations

import json
from typing import Any, Optional

from app.core.enums import Intent, Language
from app.core.llm_client import LLMClient
from app.core.schemas import ExtractedEntities, IntentResult


class LLMIntentFallbackAgent:
    """
    Gemini fallback for fuzzy banking intent/entity detection.

    This agent is only used when the rule-based intent result is weak.
    """

    MIN_USEFUL_CONFIDENCE = 0.55

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def should_use_fallback(self, rule_result: IntentResult) -> bool:
        return (
            rule_result.intent in {Intent.UNKNOWN, Intent.GENERAL}
            or rule_result.confidence < self.MIN_USEFUL_CONFIDENCE
        )

    def analyze(self, user_text: str, state: Any | None = None) -> IntentResult:
        prompt = self._build_prompt(user_text=user_text, state=state)

        payload = self.llm_client.generate_json(
            prompt=prompt,
            temperature=0.0,
            max_output_tokens=1024,
        )

        if not payload:
            return IntentResult(
                intent=Intent.UNKNOWN,
                confidence=0.0,
                entities=ExtractedEntities(),
                source=f"{self.llm_client.provider}_fallback_unavailable",
            )

        return self._payload_to_intent_result(payload)

    def _build_prompt(self, user_text: str, state: Any | None) -> str:
        valid_intents = [intent.value for intent in Intent]
        valid_languages = [language.value for language in Language]

        payload = {
            "task": "Classify the customer's latest banking call message.",
            "latest_customer_message": user_text,
            "safe_call_context": self._safe_context(state),
            "recent_history": self._safe_recent_history(state),
            "supported_intents": valid_intents,
            "supported_language_hints": valid_languages,
            "rules": [
                "Return JSON only.",
                "Choose exactly one supported intent.",
                "Do not invent amount, date, time, transaction_id, or payment_method.",
                "If the customer already paid, use payment_done.",
                "If the customer promises future payment, use promise_to_pay.",
                "If the customer says they cannot pay, use cannot_pay.",
                "If the customer asks for more time, use needs_extension.",
                "If the customer asks about late fee or penalty, use penalty_question.",
                "If the customer asks to remove or reduce late fee, use waiver_request.",
                "If the customer says loan is not theirs or unauthorized, use fraud_claim or dispute.",
                "If the customer complains about calls, staff behavior, or service, use complaint.",
                "If the customer asks for manager or human support, use escalation_request.",
                "Use hinglish when Hindi and English are mixed.",
                "If unsure, return unknown with low confidence.",
            ],
            "required_json_shape": {
                "intent": "one_supported_intent",
                "confidence": 0.0,
                "amount": None,
                "date": None,
                "time": None,
                "transaction_id": None,
                "payment_method": None,
                "complaint_reason": None,
                "dispute_reason": None,
                "kyc_field": None,
                "language_hint": "unknown",
                "reason": "short reason",
            },
        }

        return json.dumps(payload, ensure_ascii=False)

    def _safe_context(self, state: Any | None) -> dict[str, Any]:
        if state is None:
            return {}

        def enum_value(value: Any) -> Any:
            return getattr(value, "value", value)

        return {
            "phase": enum_value(getattr(state, "phase", None)),
            "identity_verified": getattr(state, "identity_verified", None),
            "last_intent": enum_value(getattr(state, "last_intent", None)),
            "payment_status": enum_value(getattr(state, "payment_status", None)),
            "outcome": getattr(state, "outcome", None),
            "outcome_detail": getattr(state, "outcome_detail", None),
        }

    def _safe_recent_history(self, state: Any | None) -> list[dict[str, str]]:
        if state is None or not hasattr(state, "recent_history"):
            return []

        try:
            turns = state.recent_history(limit=4)
        except TypeError:
            turns = state.recent_history()

        history: list[dict[str, str]] = []

        for turn in turns:
            history.append(
                {
                    "role": str(getattr(turn, "role", "unknown")),
                    "content": str(getattr(turn, "content", ""))[:240],
                }
            )

        return history

    def _payload_to_intent_result(self, payload: dict[str, Any]) -> IntentResult:
        intent = self._parse_intent(payload.get("intent"))
        confidence = self._parse_confidence(payload.get("confidence"))
        language_hint = self._parse_language(payload.get("language_hint"))

        entities = ExtractedEntities(
            amount=self._optional_float(payload.get("amount")),
            date=self._optional_str(payload.get("date")),
            time=self._optional_str(payload.get("time")),
            transaction_id=self._optional_str(payload.get("transaction_id")),
            payment_method=self._optional_str(payload.get("payment_method")),
            complaint_reason=self._optional_str(payload.get("complaint_reason")),
            dispute_reason=self._optional_str(payload.get("dispute_reason")),
            kyc_field=self._optional_str(payload.get("kyc_field")),
            language_hint=language_hint,
            raw_entities={
                "gemini_reason": self._optional_str(payload.get("reason")),
                "gemini_payload": payload,
            },
        )

        return IntentResult(
            intent=intent,
            confidence=confidence,
            entities=entities,
            source=f"{self.llm_client.provider}_fallback",
        )

    def _parse_intent(self, value: Any) -> Intent:
        try:
            return Intent(str(value))
        except ValueError:
            return Intent.UNKNOWN

    def _parse_language(self, value: Any) -> Language | None:
        if value is None:
            return None

        try:
            return Language(str(value))
        except ValueError:
            return Language.UNKNOWN

    def _parse_confidence(self, value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0

        return max(0.0, min(1.0, confidence))

    def _optional_str(self, value: Any) -> str | None:
        if value is None:
            return None

        text = str(value).strip()

        if not text or text.lower() in {"none", "null", "n/a", "unknown"}:
            return None

        return text

    def _optional_float(self, value: Any) -> float | None:
        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None