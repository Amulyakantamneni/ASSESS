# app/routers/industries.py
# Read-only browse endpoints: Industry -> Standards -> Assessment Templates.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Industry, Standard, AssessmentTemplate, FrameworkCrosswalk
from app.schemas import CrosswalkOut, CrosswalkEntry

router = APIRouter(prefix="/api", tags=["industries"])


@router.get("/industries")
async def list_industries(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Industry).order_by(Industry.name))
    industries = result.scalars().all()
    return {
        "ok": True,
        "industries": [
            {"id": i.id, "name": i.name, "slug": i.slug, "description": i.description}
            for i in industries
        ],
    }


@router.get("/industries/{industry_id}/standards")
async def list_standards(industry_id: str, db: AsyncSession = Depends(get_db)):
    industry = await db.get(Industry, industry_id)
    if not industry:
        raise HTTPException(404, "Industry not found.")
    result = await db.execute(select(Standard).where(Standard.industry_id == industry_id).order_by(Standard.name))
    standards = result.scalars().all()
    return {
        "ok": True,
        "industry": {"id": industry.id, "name": industry.name},
        "standards": [
            {"id": s.id, "name": s.name, "slug": s.slug, "description": s.description}
            for s in standards
        ],
    }


@router.get("/standards/{standard_id}/templates")
async def list_templates(standard_id: str, db: AsyncSession = Depends(get_db)):
    standard = await db.get(Standard, standard_id)
    if not standard:
        raise HTTPException(404, "Standard not found.")
    result = await db.execute(
        select(AssessmentTemplate).where(AssessmentTemplate.standard_id == standard_id).order_by(AssessmentTemplate.name)
    )
    templates = result.scalars().all()
    return {
        "ok": True,
        "standard": {"id": standard.id, "name": standard.name},
        "templates": [
            {"id": t.id, "name": t.name, "description": t.description}
            for t in templates
        ],
    }


@router.get("/standards/{standard_id}/crosswalk", response_model=CrosswalkOut)
async def get_crosswalk(standard_id: str, db: AsyncSession = Depends(get_db)):
    """Cross-framework coverage. No real mapping data exists yet (see
    FrameworkCrosswalk model), so this honestly reports unavailable rather
    than inventing coverage percentages."""
    standard = await db.get(Standard, standard_id)
    if not standard:
        raise HTTPException(404, "Standard not found.")

    rows = (
        await db.execute(select(FrameworkCrosswalk).where(FrameworkCrosswalk.standard_id == standard_id))
    ).scalars().all()

    if not rows:
        return CrosswalkOut(available=False, standard_name=standard.name, mappings=[])

    mappings = []
    for row in rows:
        mapped = await db.get(Standard, row.mapped_standard_id)
        mappings.append(CrosswalkEntry(mapped_standard_name=mapped.name if mapped else "Unknown", coverage_pct=row.coverage_pct))
    return CrosswalkOut(available=True, standard_name=standard.name, mappings=mappings)
