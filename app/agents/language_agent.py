from __future__ import annotations

import re

from app.core.enums import Language


HINDI_HINTS = [
    "haan", "han", "ji", "nahi", "matlab", "kya", "kaise", "kab",
    "paisa", "kar sakti", "kar sakta", "kar dungi", "kar dunga",
    "bol", "bol rahi", "bol raha", "baat", "theek", "abhi",
    "aaj", "shaam", "kal", "parso", "kyun", "kyu", "samajh",
    "salary nahi", "pata nahi", "mujhe", "meri", "mera",
]

TAMIL_HINTS = [
    "naan", "aama", "illa", "seri", "enna", "eppo", "panam",
    "pesuren", "tamil", "க", "ச", "ட", "த", "ந", "ம", "ய", "ர", "ல",
]


class LanguageAgent:
    def detect(self, text: str) -> Language:
        raw = text or ""
        lower = raw.lower()

        if re.search(r"[\u0900-\u097F]", raw):
            return Language.HINDI

        if re.search(r"[\u0B80-\u0BFF]", raw):
            return Language.TAMIL

        if any(hint in lower for hint in TAMIL_HINTS):
            return Language.TAMIL

        if any(hint in lower for hint in HINDI_HINTS):
            return Language.HINGLISH

        return Language.ENGLISH