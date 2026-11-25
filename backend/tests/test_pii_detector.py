from pii_detector import (Span, detect_and_redact, detect_regex, luhn_valid,
                          merge_spans, redact)


def types_found(text):
    return {s.pii_type for s in merge_spans(detect_regex(text))}


def test_email():
    assert "EMAIL" in types_found("Contact john.doe@example.com today")


def test_us_ssn():
    assert "SSN" in types_found("SSN: 123-45-6789")


def test_invalid_ssn_not_matched():
    assert "SSN" not in types_found("Ref 000-12-3456")


def test_phone_formats():
    for p in ["(555) 123-4567", "+1 555-123-4567", "+91 98765 43210", "9876543210", "+919876543210"]:
        assert "PHONE" in types_found(f"Call me at {p} please"), p


def test_credit_card_luhn():
    assert luhn_valid("4111 1111 1111 1111")
    assert not luhn_valid("4111 1111 1111 1112")
    assert "CREDIT_CARD" in types_found("Card 4111 1111 1111 1111 exp 12/27")
    assert "CREDIT_CARD" not in types_found("Card 4111 1111 1111 1112")


def test_indian_ids():
    found = types_found("Aadhaar 2345 6789 0123 and PAN ABCDE1234F")
    assert "AADHAAR" in found
    assert "PAN" in found


def test_ip_and_dob():
    found = types_found("Login from 192.168.1.10, DOB: 14/02/1999")
    assert "IP_ADDRESS" in found
    assert "DATE_OF_BIRTH" in found


def test_no_false_positives_on_plain_text():
    assert types_found("Invoice 2024 for order #12345, total Rs. 4500, qty 3") == set()


def test_merge_overlapping_spans():
    merged = merge_spans([Span(0, 10, "A"), Span(5, 20, "B"), Span(30, 35, "C")])
    assert merged == [Span(0, 20, "B"), Span(30, 35, "C")]


def test_redact_replaces_text():
    out = redact("mail a@b.com now", [Span(5, 12, "EMAIL")])
    assert out == "mail [REDACTED:EMAIL] now"


def test_detect_and_redact_counts():
    text = "Name: Ravi, email ravi@test.in, phone 9876543210, SSN 123-45-6789"
    redacted, counts, engine = detect_and_redact(text)
    assert "ravi@test.in" not in redacted
    assert "9876543210" not in redacted
    assert counts["EMAIL"] == 1 and counts["PHONE"] == 1 and counts["SSN"] == 1
    assert engine == "regex"


class FakeComprehend:
    def detect_pii_entities(self, Text, LanguageCode):
        start = Text.find("Ravi Kumar")
        return {"Entities": [{"Type": "NAME", "Score": 0.99, "BeginOffset": start,
                              "EndOffset": start + len("Ravi Kumar")}]}


class BrokenComprehend:
    def detect_pii_entities(self, **_):
        raise RuntimeError("AccessDenied")


def test_comprehend_names_are_redacted():
    redacted, counts, engine = detect_and_redact("Applicant Ravi Kumar applied", FakeComprehend())
    assert "Ravi Kumar" not in redacted
    assert counts["NAME"] == 1
    assert engine == "regex+comprehend"


def test_comprehend_failure_falls_back_to_regex():
    redacted, counts, engine = detect_and_redact("x@y.com", BrokenComprehend())
    assert engine == "regex"
    assert counts["EMAIL"] == 1
