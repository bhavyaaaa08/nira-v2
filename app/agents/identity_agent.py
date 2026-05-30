import re
from difflib import SequenceMatcher
from typing import Optional

from app.core.enums import IdentityStatus
from app.core.schemas import IdentityResult
from app.core.state import CallState


DEVANAGARI_REPLACEMENTS = {
    "हाँ": " haan ",
    "हां": " haan ",
    "हा": " haan ",
    "जी": " ji ",
    "मैं": " main ",
    "मे": " main ",
    "मेरा": " mera ",
    "मेरी": " meri ",
    "बोल रही": " bol rahi ",
    "बोल रहा": " bol raha ",
    "बोलते": " bolte ",
    "नहीं": " nahi ",
    "नही": " nahi ",
    "गलत नंबर": " wrong number ",
    "गलत": " galat ",
}


CONFIRMATION_PHRASES = {
    "yes",
    "yeah",
    "yep",
    "correct",
    "right",
    "speaking",
    "this is me",
    "that's me",
    "thats me",
    "i am",
    "i'm",
    "main",
    "haan",
    "han",
    "ha",
    "ji",
    "bol rahi",
    "bol raha",
    "ஆம்",
    "நான்",
}


WRONG_NUMBER_PHRASES = {
    "wrong number",
    "no",
    "no im not",
    "im not",
    "dont know",
    "not me",
    "wrong person",
    "i am not",
    "i'm not",
    "main nahi",
    "mai nahi",
    "galat number",
    "galat",
    "do not know",
    "don't know",
    "no such person",
    "does not live here",
}


def normalize_identity_text(text: str) -> str:
    normalized = (text or "").lower()

    for source, replacement in DEVANAGARI_REPLACEMENTS.items():
        normalized = normalized.replace(source, replacement)

    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def tokenize(text: str) -> list[str]:
    return [token for token in normalize_identity_text(text).split() if token]


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    if a in b or b in a:
        return 0.85

    return SequenceMatcher(None, a, b).ratio()


def has_any(text: str, phrases: set[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def has_confirmation_context(text: str) -> bool:
    return has_any(text, CONFIRMATION_PHRASES)


def has_wrong_number_signal(text: str) -> bool:
    return has_any(text, WRONG_NUMBER_PHRASES)


def best_name_match_score(user_text: str, expected_name: str) -> float:
    user_tokens = tokenize(user_text)
    expected_tokens = tokenize(expected_name)

    if not user_tokens or not expected_tokens:
        return 0.0

    scores = []

    for expected_token in expected_tokens:
        best_score_for_token = max(
            similarity(user_token, expected_token)
            for user_token in user_tokens
        )
        scores.append(best_score_for_token)

    return round(sum(scores) / len(scores), 2)


def first_name_match_score(user_text: str, expected_name: str) -> float:
    expected_tokens = tokenize(expected_name)

    if not expected_tokens:
        return 0.0

    first_name = expected_tokens[0]

    user_tokens = tokenize(user_text)
    if not user_tokens:
        return 0.0

    return round(max(similarity(token, first_name) for token in user_tokens), 2)


class IdentityAgent:
    """
    Identity verification agent for NIRA.

    Goal:
    - Verify customer identity before revealing account details.
    - Detect wrong number cases safely.
    - Avoid leaking loan/payment information before verification.
    """

    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts

    def verify(
        self,
        user_text: str,
        expected_customer_name: str,
        state: Optional[CallState] = None,
    ) -> IdentityResult:
        normalized = normalize_identity_text(user_text)

        if state is not None:
            state.identity_attempts += 1

        attempt_count = state.identity_attempts if state is not None else 1

        if has_wrong_number_signal(normalized):
            return IdentityResult(
                status=IdentityStatus.WRONG_NUMBER,
                verified=False,
                confidence=1.0,
                reason="Customer indicated wrong number or wrong person.",
                safe_reply=(
                    "Thank you for confirming. I will not discuss any account details on this number. "
                    "Sorry for the inconvenience."
                ),
            )

        if attempt_count > self.max_attempts:
            return IdentityResult(
                status=IdentityStatus.MAX_ATTEMPTS_EXCEEDED,
                verified=False,
                confidence=1.0,
                reason="Maximum identity verification attempts exceeded.",
                safe_reply=(
                    "I'm unable to verify your identity. For security reasons, "
                    "I cannot continue discussing this account."
                ),
            )

        full_name_score = best_name_match_score(user_text, expected_customer_name)
        first_name_score = first_name_match_score(user_text, expected_customer_name)
        has_confirmation = has_confirmation_context(normalized)

        strong_direct_confirmation = normalized in {
            "yes",
            "yeah",
            "yep",
            "correct",
            "right",
            "speaking",
            "haan",
            "han",
            "ha",
            "ji",
        }

        if has_confirmation and full_name_score >= 0.70:
            if state is not None:
                state.mark_identity_verified()

            return IdentityResult(
                status=IdentityStatus.VERIFIED,
                verified=True,
                confidence=0.95,
                reason="Customer confirmed identity with full or near-full name match.",
                safe_reply="Thank you for confirming your identity.",
                matched_name=expected_customer_name,
            )

        if has_confirmation and first_name_score >= 0.60:
            if state is not None:
                state.mark_identity_verified()

            return IdentityResult(
                status=IdentityStatus.VERIFIED,
                verified=True,
                confidence=0.88,
                reason="Customer confirmed identity with first-name match.",
                safe_reply="Thank you for confirming your identity.",
                matched_name=expected_customer_name,
            )

        if strong_direct_confirmation:
            if state is not None:
                state.mark_identity_verified()

            return IdentityResult(
                status=IdentityStatus.VERIFIED,
                verified=True,
                confidence=0.78,
                reason="Customer gave direct confirmation to identity question.",
                safe_reply="Thank you for confirming your identity.",
                matched_name=expected_customer_name,
            )

        if full_name_score >= 0.75 or first_name_score >= 0.70:
            return IdentityResult(
                status=IdentityStatus.UNCERTAIN,
                verified=False,
                confidence=0.55,
                reason="Name appears to match, but confirmation context is unclear.",
                safe_reply=(
                    f"For security, could you please confirm that you are {expected_customer_name}?"
                ),
            )

        return IdentityResult(
            status=IdentityStatus.UNCERTAIN,
            verified=False,
            confidence=0.30,
            reason="Identity could not be verified from the response.",
            safe_reply=(
                f"I can only discuss this account with {expected_customer_name}. "
                "Could you please confirm if that is you?"
            ),
        )