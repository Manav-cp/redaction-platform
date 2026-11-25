"""PII detection and redaction.

Two detectors are combined:
  1. Regex detectors (always on, zero cost) for structured PII such as emails,
     phone numbers, SSNs, credit cards (Luhn-validated), Aadhaar, PAN, IPs.
  2. Amazon Comprehend DetectPiiEntities (optional, "AI" layer) for free-form
     PII such as person names and street addresses that regex cannot catch.

Every finding is a Span(start, end, type). Overlapping spans are merged and the
text is rewritten with [REDACTED:<TYPE>] placeholders.
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    pii_type: str


# Order matters only for readability; overlaps are resolved in merge_spans().
REGEX_PATTERNS = {
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "SSN": re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
    # Indian Aadhaar: 12 digits in groups of 4, first digit 2-9
    "AADHAAR": re.compile(r"\b[2-9]\d{3}[ -]\d{4}[ -]\d{4}\b"),
    # Indian PAN: 5 letters, 4 digits, 1 letter
    "PAN": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    # 13-19 digit card numbers with optional spaces/dashes (Luhn checked later)
    "CREDIT_CARD": re.compile(r"\b(?:\d[ -]?){12,18}\d\b"),
    # International / US / Indian phone formats
    "PHONE": re.compile(
        r"(?<![\w])(?:\+?\d{1,3}[ .-]?)?(?:\(\d{2,4}\)[ .-]?|\d{2,4}[ .-])?"
        r"\d{3,5}[ .-]\d{4,5}(?![\w])"
        r"|(?<![\w])\+91[ -]?[6-9]\d{9}(?![\w])"
        r"|(?<![\w])[6-9]\d{9}(?![\w])"
    ),
    "IP_ADDRESS": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    ),
    "DATE_OF_BIRTH": re.compile(
        r"(?i)\b(?:DOB|D\.O\.B\.?|date of birth)\s*[:\-]?\s*"
        r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"
    ),
}

# Comprehend entity types we redact (others like DATE_TIME/URL are left alone).
COMPREHEND_TYPES = {
    "NAME", "ADDRESS", "EMAIL", "PHONE", "SSN", "CREDIT_DEBIT_NUMBER",
    "CREDIT_DEBIT_CVV", "CREDIT_DEBIT_EXPIRY", "BANK_ACCOUNT_NUMBER",
    "BANK_ROUTING", "PASSPORT_NUMBER", "DRIVER_ID", "IP_ADDRESS",
    "PIN", "PASSWORD", "USERNAME", "AWS_ACCESS_KEY", "AWS_SECRET_KEY",
    "IN_AADHAAR", "IN_PERMANENT_ACCOUNT_NUMBER", "IN_VOTER_NUMBER",
    "INTERNATIONAL_BANK_ACCOUNT_NUMBER", "SWIFT_CODE",
}

COMPREHEND_MAX_BYTES = 95_000  # API limit is 100 KB of UTF-8 per request


def luhn_valid(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def detect_regex(text: str) -> list:
    spans = []
    for pii_type, pattern in REGEX_PATTERNS.items():
        for m in pattern.finditer(text):
            if pii_type == "CREDIT_CARD" and not luhn_valid(m.group()):
                continue
            if pii_type == "PHONE" and sum(c.isdigit() for c in m.group()) < 10:
                continue
            spans.append(Span(m.start(), m.end(), pii_type))
    return spans


def _chunks(text: str, max_bytes: int = COMPREHEND_MAX_BYTES):
    """Yield (offset, chunk) pairs whose UTF-8 size stays under max_bytes,
    preferring to cut at newlines so entities are not split."""
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_bytes // 4)  # worst case 4 bytes/char
        # grow while still under the byte budget
        while end < n and len(text[start:end + 1000].encode("utf-8")) < max_bytes:
            end = min(n, end + 1000)
        if end < n:
            cut = text.rfind("\n", start, end)
            if cut > start:
                end = cut + 1
        yield start, text[start:end]
        start = end


def detect_comprehend(text: str, client, language: str = "en") -> list:
    spans = []
    for offset, chunk in _chunks(text):
        if not chunk.strip():
            continue
        resp = client.detect_pii_entities(Text=chunk, LanguageCode=language)
        for ent in resp.get("Entities", []):
            if ent["Type"] in COMPREHEND_TYPES and ent.get("Score", 0) >= 0.80:
                spans.append(Span(offset + ent["BeginOffset"],
                                  offset + ent["EndOffset"], ent["Type"]))
    return spans


def merge_spans(spans: list) -> list:
    """Merge overlapping spans; the longer original span names the merged one."""
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    merged = [ordered[0]]
    for s in ordered[1:]:
        last = merged[-1]
        if s.start < last.end:  # overlap
            if s.end > last.end:
                keep = last.pii_type if (last.end - last.start) >= (s.end - s.start) else s.pii_type
                merged[-1] = Span(last.start, s.end, keep)
        else:
            merged.append(s)
    return merged


def redact(text: str, spans: list) -> str:
    out = []
    cursor = 0
    for s in merge_spans(spans):
        out.append(text[cursor:s.start])
        out.append(f"[REDACTED:{s.pii_type}]")
        cursor = s.end
    out.append(text[cursor:])
    return "".join(out)


def detect_and_redact(text: str, comprehend_client=None) -> tuple:
    """Return (redacted_text, Counter of PII types, engine_used)."""
    spans = detect_regex(text)
    engine = "regex"
    if comprehend_client is not None:
        try:
            spans += detect_comprehend(text, comprehend_client)
            engine = "regex+comprehend"
        except Exception as exc:  # Comprehend unavailable / access denied
            logger.warning("Comprehend failed, falling back to regex only: %s", exc)
    merged = merge_spans(spans)
    counts = Counter(s.pii_type for s in merged)
    return redact(text, merged), counts, engine
