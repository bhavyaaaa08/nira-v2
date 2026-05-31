# test_language_agent.py  (run from project root)
from app.agents.language_agent import LanguageAgent
from app.core.enums import Language

agent = LanguageAgent()

cases = [
    ("han me anita bol rahi hu", Language.HINGLISH),
    ("yes my name is anita",     Language.ENGLISH),
    ("हाँ मैं अनिता बोल रही हूँ", Language.HINDI),
    ("naan anita pesuren",        Language.TAMIL),
]

for text, expected in cases:
    result = agent.detect(text)
    status = "✅" if result == expected else "❌"
    print(f"{status} '{text}' → got={result}, expected={expected}")