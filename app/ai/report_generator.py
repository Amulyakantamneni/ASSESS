# app/ai/report_generator.py
# Generates the narrative report via Claude, and renders it (plus the
# scorecard) into a downloadable .docx via python-docx.

import io
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.ai.claude_client import generate_structured, generate_text
from app.ai.prompt_templates import report_prompt, explain_score_prompt
from app.schemas import GeneratedReport

REPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

NAVY = RGBColor(0x0F, 0x3A, 0x7D)
GREY = RGBColor(0x6B, 0x72, 0x80)

NAVY_HEX = "#0F3A7D"
GREEN_HEX = "#10B981"
AMBER_HEX = "#F59E0B"
RED_HEX = "#EF4444"


def _score_color(score: float) -> str:
    if score >= 4:
        return GREEN_HEX
    if score >= 2.5:
        return AMBER_HEX
    return RED_HEX


def _category_chart_image(category_scores: list) -> io.BytesIO:
    """Renders a horizontal bar chart of per-category scores (0-5 scale) as a PNG."""
    labels = [str(c.get("category", "")) for c in category_scores][::-1]
    scores = [float(c.get("score", 0) or 0) for c in category_scores][::-1]
    colors = [_score_color(s) for s in scores]

    fig_height = max(2.2, 0.5 * len(labels) + 0.6)
    fig, ax = plt.subplots(figsize=(7.5, fig_height), dpi=150)
    bars = ax.barh(labels, scores, color=colors, height=0.6)

    for bar, score in zip(bars, scores):
        ax.text(min(score + 0.12, 4.75), bar.get_y() + bar.get_height() / 2, f"{score:.1f}",
                va="center", fontsize=9, color="#1F2937")

    ax.set_xlim(0, 5)
    ax.set_xlabel("Score (0 to 5)", fontsize=9, color="#6B7280")
    ax.tick_params(axis="y", labelsize=9.5, colors="#1F2937")
    ax.tick_params(axis="x", labelsize=8.5, colors="#6B7280")
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#E5E7EB")
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color="#E5E7EB", linewidth=0.7)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_report(industry: str, standard: str, template_name: str, scorecard: dict) -> GeneratedReport:
    system, user = report_prompt(industry, standard, template_name, scorecard)
    return generate_structured(system=system, user=user, schema_model=GeneratedReport, max_tokens=4096)


def explain_score(industry: str, standard: str, category: str, score: float, insight: str, recommendation: str) -> str:
    system, user = explain_score_prompt(industry, standard, category, score, insight, recommendation)
    return generate_text(system=system, user=user, max_tokens=400)


def _heading(doc: Document, text: str, size: int = 16):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    run.font.color.rgb = NAVY
    return p


def render_docx(*, assessment_id: str, industry: str, standard: str, template_name: str, scorecard: dict, report: dict) -> str:
    doc = Document()

    # Cover page
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(template_name)
    run.bold = True
    run.font.size = Pt(28)
    run.font.color.rgb = NAVY

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = subtitle.add_run(f"{industry}  |  {standard}")
    sub_run.font.size = Pt(14)
    sub_run.font.color.rgb = GREY

    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_p.add_run(datetime.now(timezone.utc).strftime("%B %d, %Y")).font.color.rgb = GREY

    doc.add_page_break()

    # Executive summary
    _heading(doc, "Executive Summary")
    doc.add_paragraph(report.get("executive_summary", ""))

    # Score overview
    _heading(doc, "Organization Score")
    score_table = doc.add_table(rows=1, cols=4)
    score_table.style = "Light Grid Accent 1"
    hdr = score_table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = (
        "Overall Score", "Maturity Level", "Compliance %", "Risk Rating"
    )
    row = score_table.add_row().cells
    row[0].text = f"{scorecard.get('overall_score', 0)}/100"
    row[1].text = str(scorecard.get("maturity_level", ""))
    row[2].text = f"{scorecard.get('compliance_pct', 0)}%"
    row[3].text = str(scorecard.get("risk_rating", ""))

    # Current state
    _heading(doc, "Current State")
    doc.add_paragraph(report.get("current_state", ""))

    # Category breakdown
    _heading(doc, "Assessment Results by Category")
    category_scores = scorecard.get("category_scores", [])
    if category_scores:
        chart_img = _category_chart_image(category_scores)
        chart_p = doc.add_paragraph()
        chart_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        chart_p.add_run().add_picture(chart_img, width=Inches(6))

    cat_table = doc.add_table(rows=1, cols=4)
    cat_table.style = "Light Grid Accent 1"
    chdr = cat_table.rows[0].cells
    chdr[0].text, chdr[1].text, chdr[2].text, chdr[3].text = ("Category", "Score", "Insight", "Recommendation")
    for c in scorecard.get("category_scores", []):
        r = cat_table.add_row().cells
        r[0].text = str(c.get("category", ""))
        r[1].text = f"{c.get('score', 0)}/5"
        r[2].text = str(c.get("insight", ""))
        r[3].text = str(c.get("recommendation", ""))

    # Compliance mapping / gaps
    _heading(doc, "Compliance Gaps")
    for g in report.get("compliance_gaps", []):
        doc.add_paragraph(g, style="List Bullet")

    _heading(doc, "Missing Requirements")
    for m in report.get("missing_requirements", []):
        doc.add_paragraph(m, style="List Bullet")

    # Strengths / risk areas
    _heading(doc, "Strengths")
    for s in scorecard.get("strengths", []):
        doc.add_paragraph(s, style="List Bullet")

    _heading(doc, "Risk Areas")
    for g in scorecard.get("gaps", []):
        doc.add_paragraph(g, style="List Bullet")

    # Roadmap
    _heading(doc, "Improvement Roadmap")
    roadmap = report.get("roadmap", {})
    for label, key in (("30-Day Action Plan", "day_30"), ("60-Day Improvement Plan", "day_60"), ("90-Day Transformation Roadmap", "day_90")):
        _heading(doc, label, size=13)
        for item in roadmap.get(key, []):
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(f"{item.get('action', '')}: ").bold = True
            p.add_run(item.get("rationale", ""))

    # Conclusion
    _heading(doc, "Conclusion")
    doc.add_paragraph(report.get("conclusion", ""))

    file_path = REPORTS_DIR / f"{assessment_id}.docx"
    doc.save(str(file_path))
    return str(file_path)


# ---------------------------------------------------------------------------
# Additional report types: Compliance, Technical, Remediation, Evidence.
# Unlike the executive report above, these are generated on demand at
# download time directly from data already in the assessment result — no
# extra Claude calls, no new DB rows, available to both tiers.
# ---------------------------------------------------------------------------

def _priority_for_gap(gap: float) -> str:
    if gap >= 2.5:
        return "Critical"
    if gap >= 1.5:
        return "High"
    if gap >= 0.75:
        return "Medium"
    return "Low"


def _evidence_status_label(status: str) -> str:
    return {
        "verified": "Verified Evidence",
        "self_reported": "Self-Reported",
        "partial": "Partial Evidence",
    }.get(status, "Self-Reported")


def _evidence_by_category(evidence_items: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = {}
    for e in evidence_items:
        grouped.setdefault(e.get("category", ""), []).append(e)
    return grouped


def _category_evidence_status(category: str, evidence_by_cat: dict) -> str:
    items = evidence_by_cat.get(category, [])
    if not items:
        return "No Evidence"
    if any(i.get("status") == "verified" for i in items):
        return "Verified Evidence"
    if any(i.get("status") == "partial" for i in items):
        return "Partial Evidence"
    return "Self-Reported"


def _add_page_number_footer(doc: Document):
    """Inserts a real Word PAGE field into the footer (renders/updates as an
    actual page number in Word, not a hardcoded string)."""
    footer = doc.sections[0].footer
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.font.size = Pt(9)
    run.font.color.rgb = GREY
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def _cover_page(doc: Document, *, report_label: str, template_name: str, industry: str, standard: str, email: str | None):
    _add_page_number_footer(doc)

    badge = doc.add_paragraph()
    badge.alignment = WD_ALIGN_PARAGRAPH.CENTER
    badge_run = badge.add_run(report_label.upper())
    badge_run.bold = True
    badge_run.font.size = Pt(11)
    badge_run.font.color.rgb = RGBColor(0x00, 0xA8, 0xE8)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(template_name)
    run.bold = True
    run.font.size = Pt(26)
    run.font.color.rgb = NAVY

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run(f"{industry}  |  {standard}").font.color.rgb = GREY

    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_p.add_run(datetime.now(timezone.utc).strftime("%B %d, %Y")).font.color.rgb = GREY

    if email:
        prepared_p = doc.add_paragraph()
        prepared_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        prepared_p.add_run(f"Prepared for: {email}").font.color.rgb = GREY

    doc.add_page_break()


def _score_overview_table(doc: Document, scorecard: dict):
    _heading(doc, "Organization Score")
    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = ("Overall Score", "Maturity Level", "Compliance %", "Risk Rating")
    row = table.add_row().cells
    row[0].text = f"{scorecard.get('overall_score', 0)}/100"
    row[1].text = str(scorecard.get("maturity_level", ""))
    row[2].text = f"{scorecard.get('compliance_pct', 0)}%"
    row[3].text = str(scorecard.get("risk_rating", ""))


def render_compliance_docx(*, assessment_id: str, industry: str, standard: str, template_name: str,
                            scorecard: dict, responses: list[dict], evidence_items: list[dict],
                            email: str | None = None) -> str:
    doc = Document()
    _cover_page(doc, report_label="Compliance Report", template_name=template_name, industry=industry, standard=standard, email=email)
    _score_overview_table(doc, scorecard)

    evidence_by_cat = _evidence_by_category(evidence_items)
    cat_by_name = {c.get("category"): c for c in scorecard.get("category_scores", [])}

    _heading(doc, "Requirements, Responses & Evidence")
    doc.add_paragraph(
        "Each row reflects what was actually assessed against this standard: the question posed, "
        "the response given, the evidence status on file, and the resulting gap and recommendation."
    )
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text, hdr[4].text = (
        "Category", "What Was Assessed", "Response", "Evidence Status", "Gap / Recommendation"
    )
    for r in responses:
        category = r.get("category", "")
        answer = r.get("answer") or {}
        answer_text = answer.get("label") or answer.get("text") or "No answer recorded"
        cat_entry = cat_by_name.get(category, {})
        row = table.add_row().cells
        row[0].text = category
        row[1].text = str(r.get("question_text", ""))
        row[2].text = str(answer_text)
        row[3].text = _category_evidence_status(category, evidence_by_cat)
        row[4].text = str(cat_entry.get("recommendation", ""))

    file_path = REPORTS_DIR / f"{assessment_id}_compliance.docx"
    doc.save(str(file_path))
    return str(file_path)


def render_technical_docx(*, assessment_id: str, industry: str, standard: str, template_name: str,
                           scorecard: dict, evidence_items: list[dict], email: str | None = None) -> str:
    doc = Document()
    _cover_page(doc, report_label="Technical Report", template_name=template_name, industry=industry, standard=standard, email=email)
    _score_overview_table(doc, scorecard)

    evidence_by_cat = _evidence_by_category(evidence_items)
    category_scores = scorecard.get("category_scores", [])

    _heading(doc, "Technical Findings by Category")
    doc.add_paragraph(
        "This report lists every assessed category with its full technical finding and evidence status. "
        "The assessment does not classify categories as technical versus non-technical, so all "
        "categories are included here for a complete technical picture."
    )
    if category_scores:
        chart_img = _category_chart_image(category_scores)
        chart_p = doc.add_paragraph()
        chart_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        chart_p.add_run().add_picture(chart_img, width=Inches(6))

    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text, hdr[4].text = (
        "Category", "Score", "Finding", "Recommendation", "Evidence"
    )
    for c in category_scores:
        row = table.add_row().cells
        row[0].text = str(c.get("category", ""))
        row[1].text = f"{c.get('score', 0)}/5"
        row[2].text = str(c.get("insight", ""))
        row[3].text = str(c.get("recommendation", ""))
        row[4].text = _category_evidence_status(c.get("category", ""), evidence_by_cat)

    file_path = REPORTS_DIR / f"{assessment_id}_technical.docx"
    doc.save(str(file_path))
    return str(file_path)


def render_remediation_docx(*, assessment_id: str, industry: str, standard: str, template_name: str,
                             scorecard: dict, email: str | None = None) -> str:
    doc = Document()
    _cover_page(doc, report_label="Remediation Report", template_name=template_name, industry=industry, standard=standard, email=email)
    _score_overview_table(doc, scorecard)

    gaps = [c for c in scorecard.get("category_scores", []) if c.get("gap", 0) > 0]
    gaps.sort(key=lambda c: c.get("gap", 0), reverse=True)

    _heading(doc, "Remediation Plan")
    if not gaps:
        doc.add_paragraph("No significant gaps were identified in this assessment.")
    else:
        table = doc.add_table(rows=1, cols=5)
        table.style = "Light Grid Accent 1"
        hdr = table.rows[0].cells
        hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text, hdr[4].text = (
            "Gap", "Priority", "Recommended Action", "Owner", "Status"
        )
        for c in gaps:
            row = table.add_row().cells
            row[0].text = str(c.get("category", ""))
            row[1].text = _priority_for_gap(c.get("gap", 0))
            row[2].text = str(c.get("recommendation", ""))
            row[3].text = "Not assigned"
            row[4].text = "Open"

    file_path = REPORTS_DIR / f"{assessment_id}_remediation.docx"
    doc.save(str(file_path))
    return str(file_path)


def render_evidence_docx(*, assessment_id: str, industry: str, standard: str, template_name: str,
                          scorecard: dict, evidence_items: list[dict], email: str | None = None) -> str:
    doc = Document()
    _cover_page(doc, report_label="Evidence Report", template_name=template_name, industry=industry, standard=standard, email=email)
    _score_overview_table(doc, scorecard)

    evidence_by_cat = _evidence_by_category(evidence_items)

    _heading(doc, "Evidence Summary by Category")
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text, hdr[4].text = (
        "Category", "Evidence Status", "Files Provided", "Description", "Gap"
    )
    for c in scorecard.get("category_scores", []):
        category = c.get("category", "")
        items = evidence_by_cat.get(category, [])
        row = table.add_row().cells
        row[0].text = category
        row[1].text = _category_evidence_status(category, evidence_by_cat)
        row[2].text = ", ".join(i.get("file_name", "") for i in items) or "None"
        row[3].text = "; ".join(i.get("description", "") for i in items if i.get("description")) or "—"
        row[4].text = f"{c.get('gap', 0)}/5"

    file_path = REPORTS_DIR / f"{assessment_id}_evidence.docx"
    doc.save(str(file_path))
    return str(file_path)
