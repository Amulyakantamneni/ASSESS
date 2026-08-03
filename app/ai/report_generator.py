# app/ai/report_generator.py
# Generates the narrative report via Claude, and renders it (plus the
# scorecard) into a downloadable .docx via python-docx.

from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.ai.claude_client import generate_structured, generate_text
from app.ai.prompt_templates import report_prompt, explain_score_prompt
from app.schemas import GeneratedReport

REPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

NAVY = RGBColor(0x0F, 0x3A, 0x7D)
GREY = RGBColor(0x6B, 0x72, 0x80)


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
            p.add_run(f"{item.get('action', '')} — ").bold = True
            p.add_run(item.get("rationale", ""))

    # Conclusion
    _heading(doc, "Conclusion")
    doc.add_paragraph(report.get("conclusion", ""))

    file_path = REPORTS_DIR / f"{assessment_id}.docx"
    doc.save(str(file_path))
    return str(file_path)
