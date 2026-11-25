import pytest

from pdf_utils import build_pdf, extract_text


def test_round_trip_text():
    pdf = build_pdf("Hello world\nSecond line with (parens) and \\ backslash", title="T")
    assert pdf.startswith(b"%PDF-1.4")
    text = extract_text(pdf)
    assert "Hello world" in text
    assert "(parens)" in text


def test_multi_page():
    body = "\n".join(f"line {i}" for i in range(200))
    text = extract_text(build_pdf(body))
    assert "line 0" in text and "line 199" in text
    assert "--- Page 3 ---" in text


def test_non_latin_characters_do_not_crash():
    pdf = build_pdf("Price ₹500 — naïve café 你好")
    assert "caf" in extract_text(pdf)


def test_invalid_pdf_raises_value_error():
    with pytest.raises(ValueError):
        extract_text(b"not a pdf at all")
