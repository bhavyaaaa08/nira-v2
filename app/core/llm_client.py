from __future__ import annotations

import json
from typing import Any, Optional
import time
import httpx
from google import genai
from google.genai import types

from app.core.config import settings


class LLMClient:
    """
    Provider-agnostic LLM client for NIRA.

    Supported providers:
    - gemini
    - groq

    Used for:
    - fuzzy intent fallback
    - Hinglish interpretation
    - later response polishing / summaries / RAG answers

    Not used for:
    - identity final verification
    - payment verification
    - risk scoring
    - compliance blocking
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self.provider = (provider or settings.llm_provider or "").strip().lower()
        self.model = model or settings.llm_model
        self.timeout_seconds = timeout_seconds or settings.llm_timeout_seconds
        self._gemini_client = self._build_gemini_client()

    def _build_gemini_client(self) -> genai.Client | None:
        if not settings.llm_enabled or self.provider != "gemini":
            return None

        if settings.google_genai_use_vertexai:
            if not settings.google_cloud_project:
                return None

            return genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
            )

        if not settings.gemini_api_key:
            return None

        return genai.Client(api_key=settings.gemini_api_key)

    def is_enabled(self) -> bool:
        if not settings.llm_enabled:
            return False

        if self.provider == "gemini":
            return self._gemini_client is not None

        if self.provider == "groq":
            return bool(settings.groq_api_key)

        return False

    def generate_json(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int = 500,
    ) -> Optional[dict[str, Any]]:
        if not self.is_enabled():
            return None

        if self.provider == "gemini":
            return self._generate_json_gemini(
                prompt=prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        if self.provider == "groq":
            return self._generate_json_groq(
                prompt=prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        return None

    def _generate_json_gemini(
        self,
        prompt: str,
        temperature: float,
        max_output_tokens: int,
    ) -> Optional[dict[str, Any]]:
        if self._gemini_client is None:
            return None

        for attempt in range(3):
            try:
                response = self._gemini_client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                    ),
                )
                print("[Gemini raw response]", response.text)
                return self._parse_json(response.text or "")

            except Exception as exc:
                print(f"[Gemini attempt {attempt + 1} failed]", type(exc).__name__, exc)

                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                    time.sleep(3)
                    continue

                return None

        return None
        

    def _generate_json_groq(
        self,
        prompt: str,
        temperature: float,
        max_output_tokens: int,
    ) -> Optional[dict[str, Any]]:
        url = f"{settings.groq_base_url.rstrip('/')}/chat/completions"

        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict JSON generator. "
                        "Return only one valid JSON object. "
                        "Do not include markdown or explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return self._parse_json(content or "")

        except Exception as exc:
            if settings.env == "development":
                print(f"[Groq error] {type(exc).__name__}: {exc}")
            return None

    @staticmethod
    def _parse_json(content: str) -> Optional[dict[str, Any]]:
        cleaned = (content or "").strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "", 1)
            cleaned = cleaned.replace("```JSON", "", 1)
            cleaned = cleaned.replace("```", "", 1)
            cleaned = cleaned.strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start == -1:
            return None

        if end == -1:
            cleaned = cleaned[start:].strip()
            cleaned = cleaned.rstrip(",")
            cleaned = cleaned + "\n}"
        else:
            cleaned = cleaned[start : end + 1]

        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError as exc:
            print("[JSON decode failed]", exc)
            print("[JSON content]", cleaned)
            return None