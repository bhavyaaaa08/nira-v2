import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from google import genai

from app.core.config import settings


def main() -> None:
    client = genai.Client(api_key=settings.gemini_api_key)

    for model in client.models.list():
        name = getattr(model, "name", "")
        actions = getattr(model, "supported_actions", None)
        methods = getattr(model, "supported_generation_methods", None)

        print(name)
        if actions:
            print("  actions:", actions)
        if methods:
            print("  methods:", methods)


if __name__ == "__main__":
    main()