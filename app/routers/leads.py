# app/routers/leads.py
# Lead capture ("Request Assessment" / "Connect With Us"). Ported from the
# Node routes/leads.js — same validation and optional Resend notification.

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Lead
from app.schemas import LeadIn, LeadOut
from app.config import RESEND_API_KEY, NOTIFY_EMAIL, NOTIFY_FROM_EMAIL

router = APIRouter(prefix="/api/leads", tags=["leads"])


async def notify_new_lead(lead: Lead):
    if not RESEND_API_KEY or not NOTIFY_EMAIL:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from": NOTIFY_FROM_EMAIL,
                    "to": NOTIFY_EMAIL,
                    "subject": f"New lead: {lead.name}",
                    "text": (
                        f"Name: {lead.name}\nEmail: {lead.email}\nCompany: {lead.company or '-'}\n"
                        f"Message: {lead.message or '-'}\nSource: {lead.source}"
                    ),
                },
            )
    except Exception:
        pass  # best-effort — never fail the lead capture because notification failed


@router.post("", response_model=dict, status_code=201)
async def create_lead(payload: LeadIn, db: AsyncSession = Depends(get_db)):
    lead = Lead(
        name=payload.name.strip(),
        email=payload.email.strip(),
        company=payload.company.strip(),
        message=payload.message.strip(),
        source=payload.source or "unknown",
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    await notify_new_lead(lead)

    return {
        "ok": True,
        "message": "Thanks! We've received your request and will be in touch shortly.",
        "leadId": lead.id,
    }


@router.get("", response_model=dict)
async def list_leads(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).order_by(Lead.created_at.desc()))
    leads = result.scalars().all()
    return {
        "ok": True,
        "count": len(leads),
        "leads": [
            {
                "id": l.id,
                "name": l.name,
                "email": l.email,
                "company": l.company,
                "message": l.message,
                "source": l.source,
                "createdAt": l.created_at.isoformat(),
            }
            for l in leads
        ],
    }
