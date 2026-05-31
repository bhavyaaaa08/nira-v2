from __future__ import annotations

import json
from typing import Optional

from app.core.enums import AgentName, Language
from app.core.llm_client import LLMClient
from app.core.state import CallState


class LocalizationAgent:
    """
    Converts final English agent responses into the customer's language.

    Business agents stay English internally.
    This agent localizes only the final customer-facing response.
    """

    agent_name = AgentName.AUTOMATION

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def localize(self, response_text: str, state: CallState) -> str:
        language = state.language

        if language == Language.ENGLISH or language == Language.UNKNOWN:
            return response_text

        if language == Language.HINGLISH:
            target = "natural Hinglish using simple Hindi words written in English script"
        elif language == Language.HINDI:
            target = "simple Hindi in Devanagari script"
        elif language == Language.TAMIL:
            target = "simple spoken Tamil"
        else:
            return response_text

        prompt = (
            f"Translate the following banking customer-service response into {target}. "
            "Rules: preserve exact meaning, keep all amounts/dates/ticket IDs unchanged, "
            "keep it short and voice-friendly, do not add any new information. "
            "Preserve exact meaning.",
            "Do not add new policy, promises, threats, or approvals.",
            "Keep amounts exactly same.",
            "Keep dates exactly same.",
            "Keep ticket IDs exactly same.",
            'Return only valid JSON in this exact shape: {"localized_response": "<translated text here>"}\n\n'
            f"Response to translate: {response_text}"
        )

        payload = self.llm_client.generate_json(
            prompt=prompt,
            temperature=0.2,
            max_output_tokens=1024,
        )

        if not payload:
            return response_text

        localized = payload.get("localized_response")

        if not localized or not isinstance(localized, str):
            return response_text

        return localized.strip()