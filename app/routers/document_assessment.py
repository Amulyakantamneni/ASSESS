# app/routers/document_assessment.py
# Controlled Document Maturity Assessment: upload a procedure/policy/standard,
# get it scored against the fixed 15-category rubric in app/ai/document_maturity.py.
# Standalone from the Industry/Standard/Template questionnaire flow in
# assessments.py — there's no questionnaire here, the document is the input.
# Open to anyone: no email requirement, no daily cap (unlike the premium-tier
# full AI report elsewhere in this app).

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.session import get_db
from app.db.models import DocumentAssessment
from app.schemas import DocumentAssessmentOut
from app.ai.document_maturity import extract_document_text, generate_document_assessment
from app.ai.document_report import render_document_assessment_docx, download_filename

router = APIRouter(prefix="/api/document-assessments", tags=["document-assessment"])

DOCS_DIR = Path(__file__).resolve().parents[2] / "data" / "document_assessments"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _row_to_out(row: DocumentAssessment) -> DocumentAssessmentOut:
    return DocumentAssessmentOut(
        id=row.id,
        document_title=row.document_title,
        original_filename=row.original_filename,
        created_at=row.created_at,
        result=row.result,
    )


@router.post("", response_model=DocumentAssessmentOut, status_code=201)
async def create_document_assessment(
    file: UploadFile = File(...),
    document_title: str = Form(""),
    email: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large. Maximum size is 15MB.")

    try:
        document_text = extract_document_text(contents, file.filename or "")
    except ValueError as e:
        raise HTTPException(400, str(e))

    title = document_title.strip() or Path(file.filename or "Document").stem

    assessment_id = uuid.uuid4().hex[:16]
    assessment_dir = DOCS_DIR / assessment_id
    assessment_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"original{ext}"
    file_path = assessment_dir / stored_name
    file_path.write_bytes(contents)

    try:
        # This is a large, multi-minute Claude call — run it off the event loop
        # thread so it doesn't stall every other request on the server while it's
        # in flight (the Anthropic SDK call itself is synchronous).
        generated = await run_in_threadpool(generate_document_assessment, title, document_text)
    except ValueError as e:
        raise HTTPException(502, str(e))
    result_dict = generated.model_dump()

    row = DocumentAssessment(
        id=assessment_id,
        email=(email.strip().lower() or None),
        document_title=title,
        original_filename=file.filename or stored_name,
        file_path=str(file_path),
        result=result_dict,
    )

    docx_path = render_document_assessment_docx(
        assessment_id=assessment_id, document_title=title, result=result_dict,
    )
    row.docx_file_path = docx_path

    db.add(row)
    await db.commit()
    await db.refresh(row)

    return _row_to_out(row)


@router.get("/{assessment_id}", response_model=DocumentAssessmentOut)
async def get_document_assessment(assessment_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.get(DocumentAssessment, assessment_id)
    if not row:
        raise HTTPException(404, "Document assessment not found.")
    return _row_to_out(row)


@router.get("/{assessment_id}/report.docx")
async def download_document_assessment_report(assessment_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.get(DocumentAssessment, assessment_id)
    if not row or not row.docx_file_path or not Path(row.docx_file_path).exists():
        raise HTTPException(404, "No downloadable report for this document assessment.")
    return FileResponse(
        row.docx_file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=download_filename(row.document_title, row.created_at),
    )
