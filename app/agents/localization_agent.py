from __future__ import annotations

from typing import Optional

from app.core.enums import AgentName, Language
from app.core.llm_client import LLMClient
from app.core.state import CallState


class LocalizationAgent:
    """
    Converts final English agent responses into the customer's language.
    Business agents stay English internally.
    """

    agent_name = AgentName.AUTOMATION

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def localize_with_trace(self, response_text: str, state: CallState) -> tuple[str, dict]:
        language = state.language

        trace = {
            "target_language": language.value,
            "localized": False,
            "fallback_used": False,
            "original_response": response_text,
            "final_response": response_text,
            "reason": "english_or_unknown",
        }

        if language == Language.ENGLISH or language == Language.UNKNOWN:
            return response_text, trace

        if language == Language.HINGLISH:
            target = "natural Hinglish using simple Hindi words written in English script"
        elif language == Language.HINDI:
            target = "simple Hindi in Devanagari script"
        elif language == Language.TAMIL:
            target = "simple spoken Tamil"
        else:
            return response_text, trace

        prompt = f"""
Translate the following banking customer-service response into {target}.

Rules:
- Preserve exact meaning.
- Keep it short and voice-friendly.
- Do not add any new information.
- Do not add new policy, promises, threats, or approvals.
- Keep amounts exactly same.
- Keep dates exactly same.
- Keep ticket IDs exactly same.

Return only valid JSON in this exact shape:
{{"localized_response": "<translated text here>"}}

Response to translate:
{response_text}
"""

        payload = self.llm_client.generate_json(
            prompt=prompt,
            temperature=0.2,
            max_output_tokens=1024,
        )

        if not payload:
            trace["fallback_used"] = True
            trace["reason"] = "llm_payload_empty"
            return response_text, trace

        localized = payload.get("localized_response")

        if not localized or not isinstance(localized, str):
            trace["fallback_used"] = True
            trace["reason"] = "localized_response_missing"
            trace["payload"] = payload
            return response_text, trace

        localized = localized.strip()

        if len(localized) < len(response_text.strip()) * 0.45:
            trace["fallback_used"] = True
            trace["reason"] = "localized_response_too_short"
            trace["payload"] = payload
            trace["attempted_localized_response"] = localized
            return response_text, trace

        trace.update(
            {
                "localized": True,
                "fallback_used": False,
                "reason": "localized_successfully",
                "payload": payload,
                "final_response": localized,
            }
        )

        return localized, trace

    def localize(self, response_text: str, state: CallState) -> str:
        localized, _trace = self.localize_with_trace(response_text, state)
        return localized