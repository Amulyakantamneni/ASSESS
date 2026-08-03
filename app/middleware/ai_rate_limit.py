# app/middleware/ai_rate_limit.py
# Enforces N AI-generated (premium) reports per email per UTC day.

from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AiReportUsage
from app.config import AI_REPORTS_PER_DAY


async def check_and_record_ai_usage(db: AsyncSession, email: str, assessment_id: str):
    today = datetime.now(timezone.utc).date()
    start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)

    result = await db.execute(
        select(func.count()).select_from(AiReportUsage).where(
            AiReportUsage.email == email.lower().strip(),
            AiReportUsage.created_at >= start,
        )
    )
    count = result.scalar_one()

    if count >= AI_REPORTS_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail=f"You've reached today's free limit ({AI_REPORTS_PER_DAY} AI reports/day). Please try again tomorrow.",
        )

    db.add(AiReportUsage(email=email.lower().strip(), assessment_id=assessment_id))
    await db.commit()
