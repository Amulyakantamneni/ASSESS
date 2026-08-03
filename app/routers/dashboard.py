# app/routers/dashboard.py
# Read-only aggregation endpoint powering the analytics dashboard.

from datetime import datetime, timedelta, timezone
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Lead, Assessment, Score, AssessmentTemplate, Standard, Industry

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _last_n_days(n: int) -> list[str]:
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def _count_by_day(rows: list[datetime], days: list[str]) -> list[int]:
    counts = Counter(d.date().isoformat() for d in rows)
    return [counts.get(day, 0) for day in days]


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    leads = (await db.execute(select(Lead))).scalars().all()
    assessments = (await db.execute(select(Assessment))).scalars().all()
    scores = (await db.execute(select(Score))).scalars().all()

    completed = [a for a in assessments if a.status == "completed"]
    days = _last_n_days(30)

    avg_overall_score = round(sum(s.overall_score for s in scores) / len(scores), 2) if scores else 0

    maturity_counts = Counter(s.maturity_level for s in scores if s.maturity_level)
    maturity_distribution = [{"level": k, "count": v} for k, v in maturity_counts.most_common()]

    gap_frequency = Counter()
    for s in scores:
        for g in (s.gaps or []):
            gap_frequency[g] += 1
    top_gaps = [{"category": k, "count": v} for k, v in gap_frequency.most_common(8)]

    # Industry / template breakdown
    template_ids = {a.template_id for a in assessments}
    templates = {}
    standards = {}
    industries = {}
    if template_ids:
        t_rows = (await db.execute(select(AssessmentTemplate).where(AssessmentTemplate.id.in_(template_ids)))).scalars().all()
        templates = {t.id: t for t in t_rows}
        standard_ids = {t.standard_id for t in t_rows}
        if standard_ids:
            s_rows = (await db.execute(select(Standard).where(Standard.id.in_(standard_ids)))).scalars().all()
            standards = {s.id: s for s in s_rows}
            industry_ids = {s.industry_id for s in s_rows}
            if industry_ids:
                i_rows = (await db.execute(select(Industry).where(Industry.id.in_(industry_ids)))).scalars().all()
                industries = {i.id: i for i in i_rows}

    industry_counts = Counter()
    for a in assessments:
        t = templates.get(a.template_id)
        s = standards.get(t.standard_id) if t else None
        i = industries.get(s.industry_id) if s else None
        if i:
            industry_counts[i.name] += 1
    by_industry = [{"industry": k, "count": v} for k, v in industry_counts.most_common()]

    tier_counts = Counter(a.tier for a in assessments)

    recent_leads = sorted(leads, key=lambda l: l.created_at, reverse=True)[:50]

    return {
        "ok": True,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "leads": len(leads),
            "assessments": len(assessments),
            "completedAssessments": len(completed),
            "completionRate": round(len(completed) / len(assessments) * 100, 1) if assessments else 0,
            "avgOverallScore": avg_overall_score,
            "freeCount": tier_counts.get("free", 0),
            "premiumCount": tier_counts.get("premium", 0),
        },
        "timeSeries": {
            "days": days,
            "leads": _count_by_day([l.created_at for l in leads], days),
            "assessments": _count_by_day([a.created_at for a in assessments], days),
        },
        "maturityLevelDistribution": maturity_distribution,
        "topGapsAggregate": top_gaps,
        "byIndustry": by_industry,
        "recentLeads": [
            {
                "id": l.id, "name": l.name, "email": l.email, "company": l.company,
                "message": l.message, "source": l.source, "createdAt": l.created_at.isoformat(),
            }
            for l in recent_leads
        ],
    }
