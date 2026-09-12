# app/ai/document_report.py
# Renders a Controlled Document Maturity Assessment result into an audit-grade
# .docx: numbered headings, a real Word TOC field, Aptos font at 9pt minimum,
# autofit-to-window tables, landscape sections for the wide tables, and
# heat-map colored score cells. Sibling to report_generator.py, which handles
# the unrelated Industry/Standard/Template questionnaire reports.

import re
from datetime import datetime, timezone

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.ai.report_generator import REPORTS_DIR, _add_page_number_footer

NAVY = RGBColor(0x0F, 0x3A, 0x7D)
GREY = RGBColor(0x6B, 0x72, 0x80)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK = RGBColor(0x1F, 0x29, 0x37)

# Score -> (fill hex, meaning, text color) per the rubric's heat-map scale.
HEAT_MAP = {
    5: ("1F4E79", "Excellent", WHITE),
    4: ("2E7D32", "Strong", WHITE),
    3: ("F2C94C", "Adequate", DARK),
    2: ("F2994A", "Weak", DARK),
    1: ("EB5757", "Critical Deficiency", WHITE),
}


def _configure_document_styles(doc: Document):
    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(9)
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.2
    for name, size, space_before in (("Heading 1", 16, 20), ("Heading 2", 13, 16), ("Heading 3", 11, 12)):
        style = doc.styles[name]
        style.font.name = "Aptos"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = NAVY
        style.paragraph_format.space_before = Pt(space_before)
        style.paragraph_format.space_after = Pt(8)


def _hex_rgb(hex_color: str) -> RGBColor:
    return RGBColor(int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def _labeled_paragraph(doc: Document, label: str, text: str):
    p = doc.add_paragraph()
    label_run = p.add_run(f"{label}: ")
    label_run.bold = True
    label_run.font.color.rgb = NAVY
    p.add_run(text or "Not addressed in the document.")
    return p


class _HeadingNumberer:
    """Tracks 1 / 1.1 / 1.1.1-style heading numbers across up to 3 levels."""

    def __init__(self):
        self._counters = [0, 0, 0]

    def next(self, level: int) -> str:
        idx = level - 1
        self._counters[idx] += 1
        for i in range(idx + 1, 3):
            self._counters[i] = 0
        return ".".join(str(c) for c in self._counters[:level])


def _heading(doc: Document, numberer: _HeadingNumberer, level: int, text: str):
    number = numberer.next(level)
    style = {1: "Heading 1", 2: "Heading 2", 3: "Heading 3"}[level]
    p = doc.add_paragraph(style=style)
    p.add_run(f"{number} {text}")
    return p


def _insert_toc_field(doc: Document):
    p = doc.add_paragraph()
    run = p.add_run()
    r = run._r

    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    fld_separate = OxmlElement("w:fldChar")
    fld_separate.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "Right-click here and choose Update Field to generate the table of contents."
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")

    r.append(fld_begin)
    r.append(instr)
    r.append(fld_separate)
    r.append(placeholder)
    r.append(fld_end)


def _set_table_autofit_window(table):
    table.autofit = True
    tbl_pr = table._tbl.tblPr
    for tag in ("w:tblW", "w:tblLayout"):
        existing = tbl_pr.find(qn(tag))
        if existing is not None:
            tbl_pr.remove(existing)
    tbl_w = OxmlElement("w:tblW")
    tbl_w.set(qn("w:type"), "pct")
    tbl_w.set(qn("w:w"), "5000")
    tbl_pr.append(tbl_w)
    tbl_layout = OxmlElement("w:tblLayout")
    tbl_layout.set(qn("w:type"), "autofit")
    tbl_pr.append(tbl_layout)


def _shade_cell(cell, hex_color: str):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    cell._tc.get_or_add_tcPr().append(shd)


def _set_cell_text(cell, text: str, color: RGBColor | None = None, bold: bool = False):
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(str(text))
    if color is not None:
        run.font.color.rgb = color
    run.font.bold = bold


def _start_landscape_section(doc: Document):
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    return section


def _start_portrait_section(doc: Document):
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    section.orientation = WD_ORIENT.PORTRAIT
    if section.page_width > section.page_height:
        section.page_width, section.page_height = section.page_height, section.page_width
    return section


def _cover_page(doc: Document, document_title: str):
    _add_page_number_footer(doc)

    badge = doc.add_paragraph()
    badge.alignment = WD_ALIGN_PARAGRAPH.CENTER
    badge_run = badge.add_run("CONTROLLED DOCUMENT MATURITY ASSESSMENT")
    badge_run.bold = True
    badge_run.font.size = Pt(11)
    badge_run.font.color.rgb = RGBColor(0x00, 0xA8, 0xE8)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(document_title)
    run.bold = True
    run.font.size = Pt(26)
    run.font.color.rgb = NAVY

    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_p.add_run(datetime.now(timezone.utc).strftime("%B %d, %Y")).font.color.rgb = GREY

    doc.add_page_break()

    toc_heading = doc.add_paragraph(style="Heading 1")
    toc_heading.add_run("Table of Contents")
    _insert_toc_field(doc)
    doc.add_page_break()


def _bullets(doc: Document, items: list[str]):
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def render_document_assessment_docx(*, assessment_id: str, document_title: str, result: dict) -> str:
    doc = Document()
    _configure_document_styles(doc)
    numberer = _HeadingNumberer()

    _cover_page(doc, document_title)

    # 1. Executive Summary
    _heading(doc, numberer, 1, "Executive Summary")

    _heading(doc, numberer, 2, "Overall Maturity Score & Level")
    score_table = doc.add_table(rows=1, cols=2)
    score_table.style = "Light Grid Accent 1"
    _set_table_autofit_window(score_table)
    hdr = score_table.rows[0].cells
    _set_cell_text(hdr[0], "Overall Maturity Score", bold=True)
    _set_cell_text(hdr[1], "Overall Maturity Level", bold=True)
    row = score_table.add_row().cells
    _set_cell_text(row[0], f"{result.get('overall_maturity_score', 0)}/5")
    _set_cell_text(row[1], result.get("overall_maturity_level", ""))

    _heading(doc, numberer, 2, "Highest & Lowest Scoring Areas")
    doc.add_paragraph("Highest scoring: " + (", ".join(result.get("highest_scoring_areas", [])) or "None"))
    doc.add_paragraph("Lowest scoring: " + (", ".join(result.get("lowest_scoring_areas", [])) or "None"))

    _heading(doc, numberer, 2, "Key Strengths & Weaknesses")
    doc.add_paragraph("Key strengths:").runs[0].bold = True
    _bullets(doc, result.get("key_strengths", []))
    doc.add_paragraph("Key weaknesses:").runs[0].bold = True
    _bullets(doc, result.get("key_weaknesses", []))

    _heading(doc, numberer, 2, "Overall Assessment")
    doc.add_paragraph(result.get("overall_assessment", ""))

    # 2. Detailed Assessment Table, wide table, landscape
    _start_landscape_section(doc)

    _heading(doc, numberer, 1, "Detailed Assessment Table")
    doc.add_paragraph(
        "Each category is scored 1 (Initial/Ad Hoc) to 5 (Optimized/Best Practice). "
        "The Heat Map column shows the color-coded rating per the legend below."
    )

    legend = doc.add_table(rows=1, cols=5)
    legend.style = "Table Grid"
    _set_table_autofit_window(legend)
    for i, score in enumerate((5, 4, 3, 2, 1)):
        fill, meaning, color = HEAT_MAP[score]
        cell = legend.rows[0].cells[i]
        _set_cell_text(cell, f"{score} — {meaning}", color=color, bold=True)
        _shade_cell(cell, fill)

    detail_table = doc.add_table(rows=1, cols=6)
    detail_table.style = "Light Grid Accent 1"
    _set_table_autofit_window(detail_table)
    hdr = detail_table.rows[0].cells
    for i, label in enumerate(("Category", "Score", "Evidence Found", "Gaps Identified", "Recommendations", "Heat Map")):
        _set_cell_text(hdr[i], label, bold=True)
    for c in result.get("category_scores", []):
        row = detail_table.add_row().cells
        score = int(c.get("score", 0) or 0)
        fill, meaning, color = HEAT_MAP.get(score, ("FFFFFF", "Unscored", DARK))
        _set_cell_text(row[0], c.get("category", ""))
        _set_cell_text(row[1], str(score), color=color, bold=True)
        _shade_cell(row[1], fill)
        _set_cell_text(row[2], c.get("evidence_found", ""))
        _set_cell_text(row[3], c.get("gaps_identified", ""))
        _set_cell_text(row[4], c.get("recommendation", ""))
        _set_cell_text(row[5], meaning, color=color, bold=True)
        _shade_cell(row[5], fill)

    # 3. Full narrative per category, back to portrait (this is prose, not a wide table)
    _start_portrait_section(doc)
    _heading(doc, numberer, 1, "Category Findings")
    doc.add_paragraph(
        "Full findings for each of the 15 categories, expanding on the summary table above."
    )
    for c in result.get("category_scores", []):
        score = int(c.get("score", 0) or 0)
        fill, meaning, _ = HEAT_MAP.get(score, ("6B7280", "Unscored", DARK))
        _heading(doc, numberer, 2, c.get("category", ""))
        score_p = doc.add_paragraph()
        score_run = score_p.add_run(f"Score: {score}/5 — {meaning}")
        score_run.bold = True
        score_run.font.color.rgb = _hex_rgb(fill)
        _labeled_paragraph(doc, "Evidence Found", c.get("evidence_found", ""))
        _labeled_paragraph(doc, "Gaps Identified", c.get("gaps_identified", ""))
        _labeled_paragraph(doc, "Recommendation", c.get("recommendation", ""))

    # 4. Top 10 Recommendations, wide table, landscape again
    _start_landscape_section(doc)
    _heading(doc, numberer, 1, "Top 10 Improvement Recommendations")
    rec_table = doc.add_table(rows=1, cols=6)
    rec_table.style = "Light Grid Accent 1"
    _set_table_autofit_window(rec_table)
    hdr = rec_table.rows[0].cells
    for i, label in enumerate((
        "Recommendation", "Business Benefit", "Risk if Not Addressed",
        "Priority", "Estimated Maturity Gain", "Quick Win",
    )):
        _set_cell_text(hdr[i], label, bold=True)
    for r in result.get("top_recommendations", []):
        row = rec_table.add_row().cells
        _set_cell_text(row[0], r.get("recommendation", ""))
        _set_cell_text(row[1], r.get("business_benefit", ""))
        _set_cell_text(row[2], r.get("risk_if_not_addressed", ""))
        _set_cell_text(row[3], r.get("priority", ""))
        _set_cell_text(row[4], r.get("estimated_maturity_gain", ""))
        _set_cell_text(row[5], "Yes" if r.get("quick_win") else "No")

    # 5. Management Conclusion, back to portrait
    _start_portrait_section(doc)
    _heading(doc, numberer, 1, "Management Conclusion")

    _heading(doc, numberer, 2, "Current Maturity Level")
    doc.add_paragraph(result.get("current_maturity_level", ""))

    _heading(doc, numberer, 2, "Target Maturity Level")
    doc.add_paragraph(result.get("target_maturity_level", ""))

    _heading(doc, numberer, 2, "Roadmap to Level 5")
    doc.add_paragraph(result.get("roadmap_to_level_5", ""))

    _heading(doc, numberer, 2, "Overall Readiness Rating")
    doc.add_paragraph(f"{result.get('overall_readiness_pct', 0)}%")

    file_path = REPORTS_DIR / f"{assessment_id}_document_assessment.docx"
    doc.save(str(file_path))
    return str(file_path)


def download_filename(document_title: str, created_at: datetime) -> str:
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", document_title.strip())
    safe = re.sub(r"_+", "_", safe).strip("_") or "Document"
    return f"{safe}_{created_at.strftime('%y%m%d')}.docx"
