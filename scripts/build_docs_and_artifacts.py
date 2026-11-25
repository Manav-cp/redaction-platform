#!/usr/bin/env python3
"""Build comprehensive RedactIQ documentation suite and generate MD, DOCX, and PDF formats."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOCS.mkdir(parents=True, exist_ok=True)

# Try importing docx and reportlab
try:
    import docx
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
    HAS_PDF = True
except ImportError:
    HAS_PDF = False


def create_docx_from_markdown_sections(filename, title, sections):
    if not HAS_DOCX:
        print(f"Skipping DOCX for {filename} (python-docx not installed)")
        return
    doc = docx.Document()

    # Style Title
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_p.add_run(title)
    title_run.font.size = Pt(22)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0, 0, 0)

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = sub_p.add_run("M.Tech Cloud Computing Final Documentation | AWS & GitHub CI/CD\nAuthor: Manav Maisuriya | Roll No: 26MCE009")
    sub_run.font.size = Pt(11)
    sub_run.font.italic = True
    sub_run.font.color.rgb = RGBColor(0, 0, 0)

    doc.add_paragraph().paragraph_format.space_after = Pt(18)

    for sec_title, sec_content, table_data in sections:
        h = doc.add_heading(sec_title, level=2)
        h.paragraph_format.space_before = Pt(14)
        h.paragraph_format.space_after = Pt(6)
        if h.runs:
            h.runs[0].font.color.rgb = RGBColor(0, 0, 0)

        if sec_content:
            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(8)
            p_run = p.add_run(sec_content)
            p_run.font.color.rgb = RGBColor(0, 0, 0)

        if table_data:
            table = doc.add_table(rows=len(table_data), cols=len(table_data[0]))
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.style = 'Table Grid'
            for r_idx, row in enumerate(table_data):
                for c_idx, cell in enumerate(row):
                    cell_p = table.cell(r_idx, c_idx).paragraphs[0]
                    cell_p.text = str(cell)
                    if cell_p.runs:
                        cell_p.runs[0].font.color.rgb = RGBColor(0, 0, 0)
                        if r_idx == 0:
                            cell_p.runs[0].font.bold = True
            doc.add_paragraph().paragraph_format.space_after = Pt(10)

    out_path = DOCS / filename
    doc.save(str(out_path))
    print(f"Generated DOCX: {out_path}")


def create_pdf_from_markdown_sections(filename, title, sections):
    if not HAS_PDF:
        print(f"Skipping PDF for {filename} (reportlab not installed)")
        return
    out_path = DOCS / filename
    doc = SimpleDocTemplate(str(out_path), pagesize=letter,
                            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()

    # Custom styles - Pure Black Typography
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.black,
        alignment=1,
        spaceAfter=8
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.black,
        alignment=1,
        spaceAfter=18
    )
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        textColor=colors.black,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=13.5,
        textColor=colors.black,
        spaceAfter=8
    )

    story = []
    story.append(Paragraph(title, title_style))
    story.append(Paragraph("M.Tech Cloud Computing Project | AWS Academy Learner Lab | RedactIQ Platform", subtitle_style))
    story.append(Spacer(1, 12))

    for sec_title, sec_content, table_data in sections:
        story.append(Paragraph(sec_title, h2_style))
        if sec_content:
            formatted_text = sec_content.replace("\n\n", "<br/><br/>").replace("\n", " ")
            story.append(Paragraph(formatted_text, body_style))

        if table_data:
            wrapped_table = []
            for row in table_data:
                wrapped_row = [Paragraph(str(cell), ParagraphStyle('TableCell', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.black)) for cell in row]
                wrapped_table.append(wrapped_row)
            
            t = Table(wrapped_table, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.white),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            story.append(t)
            story.append(Spacer(1, 8))

    doc.build(story)
    print(f"Generated PDF: {out_path}")


print("Documentation generation engine loaded successfully.")
