"""PDF helpers.

extract_text(): uses pypdf (pure Python, the maintained successor of PyPDF2).
build_pdf():    a tiny dependency-free PDF writer that lays out plain text on
                Letter-size pages with Helvetica. Writing our own avoids
                shipping native libraries inside the Lambda package.
"""

import io
import textwrap

from pypdf import PdfReader

PAGE_W, PAGE_H = 612, 792      # US Letter in points
MARGIN = 50
FONT_SIZE = 10
LEADING = 13                   # line height
WRAP_COLS = 95                 # ~ (612 - 2*50) / (10pt * 0.53 avg glyph width)
LINES_PER_PAGE = (PAGE_H - 2 * MARGIN - 30) // LEADING


def extract_text(pdf_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:
        raise ValueError("File is not a valid PDF") from exc
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("Encrypted PDFs are not supported") from exc
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        pages.append(f"--- Page {i} ---\n{page.extract_text() or ''}")
    return "\n\n".join(pages)


def _pdf_escape(line: str) -> str:
    # Helvetica with WinAnsiEncoding covers Latin-1; anything else becomes '?'
    safe = line.encode("cp1252", errors="replace").decode("cp1252")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text: str) -> list:
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\t", "    ").split("\n"):
        if not raw.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(raw, WRAP_COLS, replace_whitespace=False,
                                   drop_whitespace=True, break_long_words=True) or [""])
    return lines


def build_pdf(text: str, title: str = "Redacted document") -> bytes:
    lines = _wrap(text)
    pages = [lines[i:i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)] or [[]]

    objects = []  # index 0 -> object 1

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)

    catalog_id = add(b"")          # placeholder, filled later
    pages_id = add(b"")            # placeholder, filled later
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                  b"/Encoding /WinAnsiEncoding >>")
    bold_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
                  b"/Encoding /WinAnsiEncoding >>")

    page_ids = []
    total = len(pages)
    for n, page_lines in enumerate(pages, start=1):
        y = PAGE_H - MARGIN
        ops = [f"BT /F2 12 Tf {MARGIN} {y} Td ({_pdf_escape(title)}) Tj ET"]
        y -= 24
        ops.append(f"BT /F1 {FONT_SIZE} Tf {LEADING} TL {MARGIN} {y} Td")
        for line in page_lines:
            ops.append(f"({_pdf_escape(line)}) Tj T*")
        ops.append("ET")
        ops.append(f"BT /F1 8 Tf {PAGE_W - MARGIN - 60} {MARGIN - 20} Td "
                   f"(Page {n} of {total}) Tj ET")
        stream = "\n".join(ops).encode("cp1252", errors="replace")
        content_id = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_id = add(
            (f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
             f"/Resources << /Font << /F1 {font_id} 0 R /F2 {bold_id} 0 R >> >> "
             f"/Contents {content_id} 0 R >>").encode()
        )
        page_ids.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode()

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
              f"startxref\n{xref_pos}\n%%EOF\n".encode())
    return out.getvalue()
