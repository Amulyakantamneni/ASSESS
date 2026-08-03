# app/routers/assessments.py
# Core assessment flow: start (AI-generated questions) -> submit (AI or
# algorithmic scoring depending on tier) -> result -> report.docx -> explain-score.

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Assessment, AssessmentTemplate, Standard, Industry, Response as ResponseModel, Score, Report
from app.schemas import (
    StartAssessmentRequest, StartAssessmentResponse, QuestionOut, QuestionOption,
    SubmitAssessmentRequest, AssessmentResultOut, ScoreOut, ReportOut, Roadmap,
    ExplainScoreRequest, ExplainScoreResponse,
)
from app.ai.question_generator import generate_questions
from app.ai.scoring_engine import generate_scorecard
from app.ai import report_generator
from app.middleware.ai_rate_limit import check_and_record_ai_usage

router = APIRouter(prefix="/api/assessments", tags=["assessments"])

FREE_TIER_CATEGORIES = 5
PREMIUM_TIER_CATEGORIES = 8


async def _load_chain(db: AsyncSession, template_id: str):
    template = await db.get(AssessmentTemplate, template_id)
    if not template:
        raise HTTPException(404, "Assessment template not found.")
    standard = await db.get(Standard, template.standard_id)
    industry = await db.get(Industry, standard.industry_id)
    return template, standard, industry


@router.post("/start", response_model=StartAssessmentResponse, status_code=201)
async def start_assessment(payload: StartAssessmentRequest, db: AsyncSession = Depends(get_db)):
    template, standard, industry = await _load_chain(db, payload.template_id)

    if payload.tier == "premium" and not payload.email:
        raise HTTPException(400, "Email is required for a premium (full AI report) assessment.")

    num_categories = PREMIUM_TIER_CATEGORIES if payload.tier == "premium" else FREE_TIER_CATEGORIES
    generated = generate_questions(industry.name, standard.name, template.name, num_categories)

    questions_snapshot = []
    for idx, q in enumerate(generated.questions):
        questions_snapshot.append({
            "id": f"q{idx}",
            "category": q.category,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": [o.model_dump() for o in q.options],
        })

    assessment = Assessment(
        template_id=template.id,
        email=(payload.email.strip().lower() if payload.email else None),
        tier=payload.tier,
        status="in_progress",
        questions_snapshot=questions_snapshot,
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)

    return StartAssessmentResponse(
        assessment_id=assessment.id,
        tier=assessment.tier,
        questions=[
            QuestionOut(
                id=q["id"], category=q["category"], question_text=q["question_text"],
                question_type=q["question_type"],
                options=[QuestionOption(**o) for o in q["options"]],
            )
            for q in questions_snapshot
        ],
    )


def _algorithmic_scorecard(questions_snapshot: list[dict], answers_by_qid: dict[str, dict]) -> dict:
    """Free-tier scoring: no Claude call, derived from numeric answer values."""
    category_scores = []
    numeric_scores = []
    for q in questions_snapshot:
        ans = answers_by_qid.get(q["id"], {})
        value = ans.get("value")
        score = float(value) if isinstance(value, (int, float)) else 3.0
        score = max(1.0, min(5.0, score))
        numeric_scores.append(score)
        gap = 5.0 - score
        category_scores.append({
            "category": q["category"],
            "score": score,
            "gap": gap,
            "insight": f"Scored {score:.0f}/5 based on your response.",
            "recommendation": "Upgrade to a full AI-generated report for a tailored recommendation on this category.",
        })

    avg = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 3.0
    sorted_by_gap = sorted(category_scores, key=lambda c: c["gap"], reverse=True)
    gaps = [c["category"] for c in sorted_by_gap if c["gap"] > 0][:3]
    strengths = [c["category"] for c in sorted(category_scores, key=lambda c: c["score"], reverse=True) if c["score"] >= 4][:3]

    levels = ["Initial", "Repeatable", "Defined", "Managed", "Optimizing"]
    level = levels[min(4, max(0, round(avg) - 1))]
    risk = "low" if avg >= 4 else "medium" if avg >= 2.5 else "high"

    return {
        "overall_score": round(avg / 5 * 100, 1),
        "maturity_level": level,
        "compliance_pct": round(avg / 5 * 100, 1),
        "risk_rating": risk,
        "strengths": strengths,
        "gaps": gaps,
        "category_scores": category_scores,
    }


@router.post("/{assessment_id}/submit", response_model=AssessmentResultOut)
async def submit_assessment(assessment_id: str, payload: SubmitAssessmentRequest, db: AsyncSession = Depends(get_db)):
    assessment = await db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found.")
    if assessment.status == "completed":
        raise HTTPException(400, "This assessment has already been submitted.")

    template, standard, industry = await _load_chain(db, assessment.template_id)

    email = (payload.email or assessment.email or "").strip().lower()
    if assessment.tier == "premium" and not email:
        raise HTTPException(400, "Email is required for a premium (full AI report) assessment.")

    answers_by_qid = {a.question_id: a.answer for a in payload.responses}
    for a in payload.responses:
        db.add(ResponseModel(assessment_id=assessment.id, question_id=a.question_id, answer=a.answer, evidence_note=a.evidence_note))

    qa_pairs = [
        {
            "category": q["category"],
            "question": q["question_text"],
            "answer": answers_by_qid.get(q["id"], {}),
        }
        for q in assessment.questions_snapshot
    ]

    report_dict = None
    docx_path = None

    if assessment.tier == "premium":
        await check_and_record_ai_usage(db, email, assessment.id)
        scorecard = generate_scorecard(industry.name, standard.name, template.name, qa_pairs)
        scorecard_dict = scorecard.model_dump()
        report = report_generator.generate_report(industry.name, standard.name, template.name, scorecard_dict)
        report_dict = report.model_dump()
        docx_path = report_generator.render_docx(
            assessment_id=assessment.id, industry=industry.name, standard=standard.name,
            template_name=template.name, scorecard=scorecard_dict, report=report_dict,
        )
    else:
        scorecard_dict = _algorithmic_scorecard(assessment.questions_snapshot, answers_by_qid)

    score_row = Score(
        assessment_id=assessment.id,
        overall_score=scorecard_dict["overall_score"],
        maturity_level=scorecard_dict["maturity_level"],
        compliance_pct=scorecard_dict["compliance_pct"],
        risk_rating=scorecard_dict["risk_rating"],
        strengths=scorecard_dict["strengths"],
        gaps=scorecard_dict["gaps"],
        category_scores=scorecard_dict["category_scores"],
    )
    db.add(score_row)

    if report_dict is not None:
        db.add(Report(
            assessment_id=assessment.id,
            executive_summary=report_dict["executive_summary"],
            detailed_analysis={
                "current_state": report_dict["current_state"],
                "missing_requirements": report_dict["missing_requirements"],
                "compliance_gaps": report_dict["compliance_gaps"],
                "conclusion": report_dict["conclusion"],
            },
            roadmap_30_60_90=report_dict["roadmap"],
            docx_file_path=docx_path,
        ))

    assessment.status = "completed"
    assessment.email = email or assessment.email
    assessment.completed_at = datetime.now(timezone.utc)
    await db.commit()

    return await _build_result(db, assessment.id)


async def _build_result(db: AsyncSession, assessment_id: str) -> AssessmentResultOut:
    assessment = await db.get(Assessment, assessment_id)
    template, standard, industry = await _load_chain(db, assessment.template_id)

    score = (await db.execute(select(Score).where(Score.assessment_id == assessment_id))).scalar_one_or_none()
    report = (await db.execute(select(Report).where(Report.assessment_id == assessment_id))).scalar_one_or_none()

    score_out = None
    if score:
        score_out = ScoreOut(
            overall_score=score.overall_score, maturity_level=score.maturity_level,
            compliance_pct=score.compliance_pct, risk_rating=score.risk_rating,
            strengths=score.strengths, gaps=score.gaps, category_scores=score.category_scores,
        )

    report_out = None
    if report:
        da = report.detailed_analysis or {}
        report_out = ReportOut(
            executive_summary=report.executive_summary,
            current_state=da.get("current_state", ""),
            missing_requirements=da.get("missing_requirements", []),
            compliance_gaps=da.get("compliance_gaps", []),
            roadmap=Roadmap(**report.roadmap_30_60_90),
            conclusion=da.get("conclusion", ""),
        )

    return AssessmentResultOut(
        assessment_id=assessment.id,
        template_name=template.name,
        industry_name=industry.name,
        standard_name=standard.name,
        tier=assessment.tier,
        score=score_out,
        report=report_out,
    )


@router.get("/{assessment_id}/result", response_model=AssessmentResultOut)
async def get_result(assessment_id: str, db: AsyncSession = Depends(get_db)):
    assessment = await db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found.")
    return await _build_result(db, assessment_id)


@router.get("/{assessment_id}/report.docx")
async def download_report(assessment_id: str, db: AsyncSession = Depends(get_db)):
    report = (await db.execute(select(Report).where(Report.assessment_id == assessment_id))).scalar_one_or_none()
    if not report or not report.docx_file_path or not Path(report.docx_file_path).exists():
        raise HTTPException(404, "No downloadable report for this assessment (available for premium assessments only).")
    return FileResponse(
        report.docx_file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"assessment-report-{assessment_id}.docx",
    )


@router.post("/{assessment_id}/explain-score", response_model=ExplainScoreResponse)
async def explain_score_endpoint(assessment_id: str, payload: ExplainScoreRequest, db: AsyncSession = Depends(get_db)):
    assessment = await db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found.")
    template, standard, industry = await _load_chain(db, assessment.template_id)
    score = (await db.execute(select(Score).where(Score.assessment_id == assessment_id))).scalar_one_or_none()
    if not score:
        raise HTTPException(404, "This assessment has no score yet.")

    entry = next((c for c in score.category_scores if c["category"] == payload.category), None)
    if not entry:
        raise HTTPException(404, "Category not found in this assessment's scorecard.")

    explanation = report_generator.explain_score(
        industry.name, standard.name, payload.category, entry["score"], entry["insight"], entry["recommendation"],
    )
    return ExplainScoreResponse(explanation=explanation)
