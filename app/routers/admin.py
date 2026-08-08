# app/routers/admin.py
# Single shared admin login (session cookie) + CRUD for industries/
# standards/templates/questions, plus an analytics view.

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Industry, Standard, AssessmentTemplate, Question, Evidence
from app.schemas import AdminLoginRequest, IndustryIn, StandardIn, TemplateIn, QuestionIn
from app.middleware.admin_auth import require_admin
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD_HASH

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Dev fallback (password "admin") so the portal is usable before ADMIN_PASSWORD_HASH is configured.
_DEV_FALLBACK_HASH = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode()


@router.post("/login")
async def admin_login(payload: AdminLoginRequest, request: Request):
    expected_hash = ADMIN_PASSWORD_HASH or _DEV_FALLBACK_HASH
    valid_user = payload.username == ADMIN_USERNAME
    valid_pass = bcrypt.checkpw(payload.password.encode()[:72], expected_hash.encode())
    if not (valid_user and valid_pass):
        raise HTTPException(401, "Invalid admin credentials.")
    request.session["is_admin"] = True
    return {"ok": True}


@router.post("/logout")
async def admin_logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/session")
async def admin_session(request: Request):
    return {"ok": True, "isAdmin": bool(request.session.get("is_admin"))}


# ---------- Industries ----------

@router.get("/industries", dependencies=[Depends(require_admin)])
async def admin_list_industries(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Industry).order_by(Industry.name))
    return {"ok": True, "industries": [
        {"id": i.id, "name": i.name, "slug": i.slug, "description": i.description} for i in result.scalars().all()
    ]}


@router.post("/industries", dependencies=[Depends(require_admin)], status_code=201)
async def admin_create_industry(payload: IndustryIn, db: AsyncSession = Depends(get_db)):
    industry = Industry(name=payload.name, slug=payload.slug, description=payload.description)
    db.add(industry)
    await db.commit()
    await db.refresh(industry)
    return {"ok": True, "id": industry.id}


@router.put("/industries/{industry_id}", dependencies=[Depends(require_admin)])
async def admin_update_industry(industry_id: str, payload: IndustryIn, db: AsyncSession = Depends(get_db)):
    industry = await db.get(Industry, industry_id)
    if not industry:
        raise HTTPException(404, "Industry not found.")
    industry.name, industry.slug, industry.description = payload.name, payload.slug, payload.description
    await db.commit()
    return {"ok": True}


@router.delete("/industries/{industry_id}", dependencies=[Depends(require_admin)])
async def admin_delete_industry(industry_id: str, db: AsyncSession = Depends(get_db)):
    industry = await db.get(Industry, industry_id)
    if not industry:
        raise HTTPException(404, "Industry not found.")
    await db.delete(industry)
    await db.commit()
    return {"ok": True}


# ---------- Standards ----------

@router.get("/standards", dependencies=[Depends(require_admin)])
async def admin_list_standards(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Standard).order_by(Standard.name))
    return {"ok": True, "standards": [
        {"id": s.id, "industryId": s.industry_id, "name": s.name, "slug": s.slug, "description": s.description}
        for s in result.scalars().all()
    ]}


@router.post("/standards", dependencies=[Depends(require_admin)], status_code=201)
async def admin_create_standard(payload: StandardIn, db: AsyncSession = Depends(get_db)):
    if not await db.get(Industry, payload.industry_id):
        raise HTTPException(400, "Unknown industry_id.")
    standard = Standard(industry_id=payload.industry_id, name=payload.name, slug=payload.slug, description=payload.description)
    db.add(standard)
    await db.commit()
    await db.refresh(standard)
    return {"ok": True, "id": standard.id}


@router.put("/standards/{standard_id}", dependencies=[Depends(require_admin)])
async def admin_update_standard(standard_id: str, payload: StandardIn, db: AsyncSession = Depends(get_db)):
    standard = await db.get(Standard, standard_id)
    if not standard:
        raise HTTPException(404, "Standard not found.")
    standard.industry_id, standard.name, standard.slug, standard.description = (
        payload.industry_id, payload.name, payload.slug, payload.description
    )
    await db.commit()
    return {"ok": True}


@router.delete("/standards/{standard_id}", dependencies=[Depends(require_admin)])
async def admin_delete_standard(standard_id: str, db: AsyncSession = Depends(get_db)):
    standard = await db.get(Standard, standard_id)
    if not standard:
        raise HTTPException(404, "Standard not found.")
    await db.delete(standard)
    await db.commit()
    return {"ok": True}


# ---------- Assessment Templates ----------

@router.get("/templates", dependencies=[Depends(require_admin)])
async def admin_list_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AssessmentTemplate).order_by(AssessmentTemplate.name))
    return {"ok": True, "templates": [
        {"id": t.id, "standardId": t.standard_id, "name": t.name, "description": t.description}
        for t in result.scalars().all()
    ]}


@router.post("/templates", dependencies=[Depends(require_admin)], status_code=201)
async def admin_create_template(payload: TemplateIn, db: AsyncSession = Depends(get_db)):
    if not await db.get(Standard, payload.standard_id):
        raise HTTPException(400, "Unknown standard_id.")
    template = AssessmentTemplate(standard_id=payload.standard_id, name=payload.name, description=payload.description)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return {"ok": True, "id": template.id}


@router.delete("/templates/{template_id}", dependencies=[Depends(require_admin)])
async def admin_delete_template(template_id: str, db: AsyncSession = Depends(get_db)):
    template = await db.get(AssessmentTemplate, template_id)
    if not template:
        raise HTTPException(404, "Template not found.")
    await db.delete(template)
    await db.commit()
    return {"ok": True}


# ---------- Questions (optional static seed bank; AI generation is the primary path) ----------

@router.get("/questions", dependencies=[Depends(require_admin)])
async def admin_list_questions(template_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Question).where(Question.template_id == template_id).order_by(Question.order_index)
    )
    return {"ok": True, "questions": [
        {
            "id": q.id, "category": q.category, "questionText": q.question_text,
            "questionType": q.question_type, "options": q.options, "orderIndex": q.order_index,
        }
        for q in result.scalars().all()
    ]}


@router.post("/questions", dependencies=[Depends(require_admin)], status_code=201)
async def admin_create_question(payload: QuestionIn, db: AsyncSession = Depends(get_db)):
    if not await db.get(AssessmentTemplate, payload.template_id):
        raise HTTPException(400, "Unknown template_id.")
    question = Question(
        template_id=payload.template_id, category=payload.category, question_text=payload.question_text,
        question_type=payload.question_type, options=[o.model_dump() for o in payload.options],
        order_index=payload.order_index,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return {"ok": True, "id": question.id}


@router.delete("/questions/{question_id}", dependencies=[Depends(require_admin)])
async def admin_delete_question(question_id: str, db: AsyncSession = Depends(get_db)):
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "Question not found.")
    await db.delete(question)
    await db.commit()
    return {"ok": True}


# ---------- Evidence verification ----------
# The only real "verified" state transition in the system — deliberately manual,
# never automatic, per the evidence spec ("uploading means provided, not verified").

@router.post("/evidence/{evidence_id}/verify", dependencies=[Depends(require_admin)])
async def admin_verify_evidence(evidence_id: str, db: AsyncSession = Depends(get_db)):
    evidence = await db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(404, "Evidence not found.")
    evidence.status = "verified"
    await db.commit()
    return {"ok": True, "status": evidence.status}
