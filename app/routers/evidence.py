# app/routers/evidence.py
# Evidence uploads for assessment categories. Uploading a file marks evidence
# as "provided" (self_reported), never "verified" — verification is a manual
# admin action via the existing admin session auth.

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Assessment, Evidence
from app.schemas import EvidenceOut

router = APIRouter(prefix="/api/assessments", tags=["evidence"])

EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".txt"}
ALLOWED_STATUSES = {"self_reported", "partial"}  # "verified" is admin-only


@router.post("/{assessment_id}/evidence", response_model=EvidenceOut, status_code=201)
async def upload_evidence(
    assessment_id: str,
    category: str = Form(...),
    description: str = Form(""),
    status: str = Form("self_reported"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    assessment = await db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found.")

    if status not in ALLOWED_STATUSES:
        status = "self_reported"

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large. Maximum size is 10MB.")

    assessment_dir = EVIDENCE_DIR / assessment_id
    assessment_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex[:12]}_{Path(file.filename or 'upload').name}"
    file_path = assessment_dir / stored_name
    file_path.write_bytes(contents)

    evidence = Evidence(
        assessment_id=assessment_id,
        category=category,
        file_name=file.filename or stored_name,
        file_path=str(file_path),
        content_type=file.content_type or "",
        status=status,
        description=description,
    )
    db.add(evidence)
    await db.commit()
    await db.refresh(evidence)
    return EvidenceOut(**{k: getattr(evidence, k) for k in EvidenceOut.model_fields})


@router.get("/{assessment_id}/evidence", response_model=list[EvidenceOut])
async def list_evidence(assessment_id: str, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(Evidence).where(Evidence.assessment_id == assessment_id).order_by(Evidence.uploaded_at.desc()))
    ).scalars().all()
    return [EvidenceOut(**{k: getattr(e, k) for k in EvidenceOut.model_fields}) for e in rows]


@router.get("/{assessment_id}/evidence/{evidence_id}/file")
async def download_evidence_file(assessment_id: str, evidence_id: str, db: AsyncSession = Depends(get_db)):
    evidence = await db.get(Evidence, evidence_id)
    if not evidence or evidence.assessment_id != assessment_id or not Path(evidence.file_path).exists():
        raise HTTPException(404, "Evidence file not found.")
    return FileResponse(evidence.file_path, media_type=evidence.content_type or "application/octet-stream", filename=evidence.file_name)
