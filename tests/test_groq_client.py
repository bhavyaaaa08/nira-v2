import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.llm_client import LLMClient


def main() -> None:
    print("LLM enabled setting:", settings.llm_enabled)
    print("LLM provider:", settings.llm_provider)
    print("LLM model:", settings.llm_model)
    print("Groq key present:", bool(settings.groq_api_key))
    print("Groq key starts with:", settings.groq_api_key[:4] if settings.groq_api_key else "missing")

    client = LLMClient()

    print("Client enabled:", client.is_enabled())

    result = client.generate_json(
        prompt='Return JSON only: {"status": "ok", "provider": "groq"}',
        temperature=0.0,
        max_output_tokens=80,
    )

    print("Groq result:", result)

    if result is None:
        raise SystemExit("Groq test failed.")

    print("Groq test passed.")


if __name__ == "__main__":
    main()