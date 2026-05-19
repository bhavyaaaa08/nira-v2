import re
from typing import Optional

from app.core.enums import Intent, Language
from app.core.schemas import ExtractedEntities, IntentResult


DEVANAGARI_REPLACEMENTS = {
    "हाँ": " haan ",
    "हां": " haan ",
    "हा": " haan ",
    "जी": " ji ",
    "मैं": " main ",
    "मेरी": " meri ",
    "मेरा": " mera ",
    "नहीं": " nahi ",
    "नही": " nahi ",
    "पेमेंट": " payment ",
    "भुगतान": " payment ",
    "पैसा": " paisa ",
    "रुपये": " rupees ",
    "आज": " aaj ",
    "कल": " kal ",
    "परसों": " parso ",
    "शाम": " shaam ",
    "सुबह": " subah ",
    "रात": " raat ",
    "दोपहर": " dopahar ",
    "लेट फीस": " late fee ",
    "लेट फी": " late fee ",
    "जुर्माना": " penalty ",
    "माफ": " maaf ",
    "माफ़": " maaf ",
    "हटा": " hata ",
    "हट": " hata ",
    "गलत": " galat ",
    "शिकायत": " complaint ",
    "फ्रॉड": " fraud ",
    "धोखा": " fraud ",
    "आधार": " aadhaar ",
    "पैन": " pan ",
}


PAYMENT_WORDS = [
    "payment",
    "pay",
    "paid",
    "paisa",
    "amount",
    "emi",
    "installment",
    "upi",
    "transfer",
    "bank",
    "loan app",
]

COMMITMENT_WORDS = [
    "will pay",
    "i'll pay",
    "i will pay",
    "pay kar dunga",
    "pay kar dungi",
    "payment kar dunga",
    "payment kar dungi",
    "kar dunga",
    "kar dungi",
    "kar denge",
    "de dunga",
    "de dungi",
    "jama kar",
    "transfer kar",
    "clear kar",
]

TIME_WORDS = [
    "today",
    "aaj",
    "tonight",
    "raat",
    "evening",
    "shaam",
    "morning",
    "subah",
    "tomorrow",
    "kal",
    "parso",
    "day after tomorrow",
    "friday",
    "monday",
    "next week",
    "end of week",
]

PAYMENT_DONE_PHRASES = [
    "already paid",
    "paid already",
    "payment done",
    "done the payment",
    "payment ho gaya",
    "payment kar diya",
    "pay kar diya",
    "transfer kar diya",
    "bhej diya",
    "sent the money",
    "i have paid",
    "i paid",
]

PAYMENT_METHOD_PHRASES = [
    "how do i pay",
    "how to pay",
    "payment kaise",
    "kaise pay",
    "upi se",
    "through upi",
    "bank transfer",
    "payment portal",
    "which app",
    "loan app",
    "app se",
]

PARTIAL_PAYMENT_PHRASES = [
    "partial payment",
    "part payment",
    "half payment",
    "can pay half",
    "pay half",
    "aadha",
    "thoda pay",
    "some amount",
    "part of the amount",
]

CANNOT_PAY_PHRASES = [
    "cannot pay",
    "can't pay",
    "cant pay",
    "unable to pay",
    "no money",
    "paisa nahi",
    "paise nahi",
    "abhi nahi de sakta",
    "abhi nahi de sakti",
    "not able to pay",
    "financial problem",
]

EXTENSION_PHRASES = [
    "need more time",
    "more time",
    "extension",
    "extend",
    "few more days",
    "another week",
    "thoda time",
    "time chahiye",
    "baad mein",
]

PENALTY_QUESTION_PHRASES = [
    "why late fee",
    "why penalty",
    "why charge",
    "late fee kya",
    "penalty kya",
    "fee kyun",
    "charge kyun",
    "what is this charge",
    "what is late fee",
]

WAIVER_PHRASES = [
    "waive",
    "remove",
    "reverse",
    "cancel",
    "hata",
    "maaf",
    "kam",
]

ESCALATION_PHRASES = [
    "human agent",
    "talk to human",
    "speak to someone",
    "connect me",
    "manager",
    "senior",
    "supervisor",
    "executive",
    "agent se baat",
    "insaan se baat",
]

DISPUTE_PHRASES = [
    "wrong amount",
    "galat amount",
    "this is wrong",
    "galat hai",
    "i don't have a loan",
    "i never took this loan",
    "loan nahi liya",
    "not my loan",
    "not mine",
    "mistake",
]

FRAUD_PHRASES = [
    "fraud",
    "scam",
    "unauthorized",
    "not authorized",
    "someone else took",
    "identity theft",
    "dhoka",
    "dhokha",
    "fake loan",
]

COMPLAINT_PHRASES = [
    "complaint",
    "complain",
    "harassment",
    "stop calling",
    "baar baar call",
    "again and again",
    "too many calls",
    "rude",
    "bad service",
    "consumer court",
]

KYC_PHRASES = [
    "kyc",
    "aadhaar",
    "aadhar",
    "pan",
    "address change",
    "mobile number change",
    "phone number change",
    "name correction",
    "update my number",
    "update address",
]

CLOSING_PHRASES = [
    "bye",
    "goodbye",
    "that's all",
    "nothing else",
    "bas",
    "theek hai bye",
    "ok thanks bye",
    "thank you bye",
]


def normalize_text(text: str) -> str:
    normalized = (text or "").lower()

    for source, replacement in DEVANAGARI_REPLACEMENTS.items():
        normalized = normalized.replace(source, replacement)

    normalized = re.sub(r"[^\w\s:./-]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def detect_language_hint(text: str) -> Language:
    original = text or ""
    normalized = normalize_text(text)

    if re.search(r"[\u0B80-\u0BFF]", original):
        return Language.TAMIL

    if re.search(r"[\u0900-\u097F]", original):
        return Language.HINDI

    hinglish_hints = [
        "haan",
        "nahi",
        "kya",
        "kaise",
        "kab",
        "paisa",
        "aaj",
        "kal",
        "shaam",
        "subah",
        "main",
        "kar dungi",
        "kar dunga",
        "theek",
    ]

    if has_any(normalized, hinglish_hints):
        return Language.HINGLISH

    english_hints = [
        "hello",
        "yes",
        "payment",
        "loan",
        "amount",
        "paid",
        "tomorrow",
        "today",
        "complaint",
    ]

    if has_any(normalized, english_hints):
        return Language.ENGLISH

    return Language.UNKNOWN


def extract_amount(text: str) -> Optional[float]:
    normalized = normalize_text(text)

    patterns = [
        r"(?:rs\.?|inr|₹)\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:rs\.?|rupees|inr|₹)",
        r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:ka|ki)?\s*(?:payment|amount|emi)",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            raw_amount = match.group(1).replace(",", "")
            try:
                return float(raw_amount)
            except ValueError:
                return None

    return None


def extract_time(text: str) -> Optional[str]:
    normalized = normalize_text(text)

    range_match = re.search(
        r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*(?:to|-|and)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b",
        normalized,
    )
    if range_match:
        return f"{range_match.group(1)} - {range_match.group(2)}"

    time_match = re.search(
        r"\b(?:at|by|around|before)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b",
        normalized,
    )
    if time_match:
        return time_match.group(1)

    if "shaam" in normalized or "evening" in normalized:
        return "evening"

    if "subah" in normalized or "morning" in normalized:
        return "morning"

    if "raat" in normalized or "tonight" in normalized or "night" in normalized:
        return "night"

    if "dopahar" in normalized or "afternoon" in normalized:
        return "afternoon"

    return None


def extract_date(text: str) -> Optional[str]:
    normalized = normalize_text(text)

    if "yesterday" in normalized or "kal paid" in normalized or "paid kal" in normalized:
        return "yesterday"

    if "day after tomorrow" in normalized or "parso" in normalized:
        return "day_after_tomorrow"

    if "tomorrow" in normalized or "kal" in normalized:
        return "tomorrow"

    if "today" in normalized or "aaj" in normalized:
        return "today"

    if "next week" in normalized:
        return "next_week"

    if "end of week" in normalized or "by friday" in normalized:
        return "end_of_week"

    date_match = re.search(
        r"\b(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b",
        normalized,
    )
    if date_match:
        return date_match.group(1)

    return None


def extract_transaction_id(text: str) -> Optional[str]:
    normalized = normalize_text(text)

    patterns = [
        r"(?:transaction id|txn id|reference number|ref number|utr|upi ref|transaction reference)\s*(?:is|:)?\s*([a-z0-9-]{6,})",
        r"\b(utr[a-z0-9-]{6,})\b",
        r"\b(txn[a-z0-9-]{6,})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return match.group(1).upper()

    return None


def extract_payment_method(text: str) -> Optional[str]:
    normalized = normalize_text(text)

    if "upi" in normalized:
        return "upi"

    if "bank transfer" in normalized or "neft" in normalized or "imps" in normalized:
        return "bank_transfer"

    if "loan app" in normalized or "app" in normalized:
        return "loan_app"

    if "portal" in normalized or "website" in normalized:
        return "payment_portal"

    return None


def extract_kyc_field(text: str) -> Optional[str]:
    normalized = normalize_text(text)

    if "mobile" in normalized or "phone" in normalized or "number" in normalized:
        return "mobile_number"

    if "address" in normalized:
        return "address"

    if "aadhaar" in normalized or "aadhar" in normalized:
        return "aadhaar"

    if "pan" in normalized:
        return "pan"

    if "name" in normalized:
        return "name"

    return None


def has_payment_commitment(text: str) -> bool:
    normalized = normalize_text(text)

    return (
        has_any(normalized, PAYMENT_WORDS)
        and (
            has_any(normalized, COMMITMENT_WORDS)
            or has_any(normalized, TIME_WORDS)
        )
    )


def has_waiver_request(text: str) -> bool:
    normalized = normalize_text(text)

    fee_mentioned = has_any(normalized, ["late fee", "fee", "penalty", "charge"])
    waiver_asked = has_any(normalized, WAIVER_PHRASES)

    return fee_mentioned and waiver_asked


def detect_intent(text: str) -> Intent:
    normalized = normalize_text(text)

    if has_any(normalized, CLOSING_PHRASES):
        return Intent.CLOSING

    if has_any(normalized, ESCALATION_PHRASES):
        return Intent.ESCALATION_REQUEST

    if has_any(normalized, COMPLAINT_PHRASES):
        return Intent.COMPLAINT

    if has_any(normalized, FRAUD_PHRASES):
        return Intent.FRAUD_CLAIM

    if has_any(normalized, DISPUTE_PHRASES):
        return Intent.DISPUTE

    if has_any(normalized, KYC_PHRASES):
        return Intent.KYC_UPDATE

    if has_any(normalized, PAYMENT_DONE_PHRASES):
        return Intent.PAYMENT_DONE

    if has_any(normalized, PAYMENT_METHOD_PHRASES):
        return Intent.PAYMENT_METHOD

    if has_waiver_request(normalized):
        return Intent.WAIVER_REQUEST

    if has_any(normalized, PENALTY_QUESTION_PHRASES):
        return Intent.PENALTY_QUESTION

    if has_any(normalized, PARTIAL_PAYMENT_PHRASES):
        return Intent.PARTIAL_PAYMENT

    if has_any(normalized, CANNOT_PAY_PHRASES):
        return Intent.CANNOT_PAY

    if has_any(normalized, EXTENSION_PHRASES):
        return Intent.NEEDS_EXTENSION

    if has_payment_commitment(normalized):
        return Intent.PROMISE_TO_PAY

    return Intent.GENERAL


def build_entities(text: str) -> ExtractedEntities:
    normalized = normalize_text(text)

    return ExtractedEntities(
        amount=extract_amount(text),
        date=extract_date(text),
        time=extract_time(text),
        transaction_id=extract_transaction_id(text),
        payment_method=extract_payment_method(text),
        complaint_reason=text if has_any(normalized, COMPLAINT_PHRASES) else None,
        dispute_reason=text if has_any(normalized, DISPUTE_PHRASES + FRAUD_PHRASES) else None,
        kyc_field=extract_kyc_field(text),
        language_hint=detect_language_hint(text),
        raw_entities={
            "normalized_text": normalized,
        },
    )


class IntentEntityAgent:
    """
    Rule-based intent and entity extraction agent for NIRA.

    This is intentionally deterministic for call-control decisions.
    LLM-based fallback can be added later, but core banking intents should
    remain predictable and testable.
    """

    def analyze(self, text: str) -> IntentResult:
        intent = detect_intent(text)
        entities = build_entities(text)

        confidence = 1.0 if intent != Intent.GENERAL else 0.45

        return IntentResult(
            intent=intent,
            confidence=confidence,
            entities=entities,
            source="rule_based",
        )