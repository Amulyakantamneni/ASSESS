# app/routers/document_assessment.py
# Controlled Document Maturity Assessment: upload a procedure/policy/standard,
# review the extracted context, then get it scored against the fixed
# 15-category rubric in app/ai/document_maturity.py. Standalone from the
# Industry/Standard/Template questionnaire flow in assessments.py — there's no
# questionnaire here, the document is the input. Open to anyone: no email
# requirement, no daily cap (unlike the premium-tier full AI report elsewhere
# in this app).
#
# Two-phase flow, matching the UI's upload -> review -> assess steps. Both
# phases run as a background task, not inline in the request: the Claude
# calls take minutes, and a platform reverse proxy (e.g. Render's) will kill
# a request held open that long and hand the frontend a non-JSON timeout
# page instead of a real response. So:
#   POST /extract         -> returns almost immediately, status=extracting
#   GET /{id}              -> poll this for status -> extracted (or failed)
#   POST /{id}/assess      -> returns almost immediately, status=assessing
#   GET /{id}              -> poll this for status -> assessed (or failed)

import logging
import uuid
from pathlib import Path

import anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.session import SessionLocal, get_db
from app.db.models import DocumentAssessment
from app.schemas import DocumentAssessmentOut, AssessFromContextRequest, ExtractedContext
from app.ai.document_ingest import extract_document_text
from app.ai.document_extraction import extract_context
from app.ai.document_maturity import generate_document_assessment
from app.ai.document_report import render_document_assessment_docx, download_filename

router = APIRouter(prefix="/api/document-assessments", tags=["document-assessment"])

DOCS_DIR = Path(__file__).resolve().parents[2] / "data" / "document_assessments"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

logger = logging.getLogger(__name__)

AI_UNAVAILABLE_MESSAGE = (
    "The AI service is temporarily unavailable. Please try again in a few minutes."
)


def _row_to_out(row: DocumentAssessment) -> DocumentAssessmentOut:
    return DocumentAssessmentOut(
        id=row.id,
        document_title=row.document_title,
        original_filename=row.original_filename,
        created_at=row.created_at,
        status=row.status,
        error_message=row.error_message,
        extracted_context=row.extracted_context or None,
        result=row.result or None,
    )


async def _run_extraction(assessment_id: str, contents: bytes, filename: str, title: str):
    async with SessionLocal() as db:
        row = await db.get(DocumentAssessment, assessment_id)
        if not row:
            return
        try:
            document_text = await run_in_threadpool(extract_document_text, contents, filename)
            context = await run_in_threadpool(extract_context, title, document_text)
        except ValueError as e:
            row.status, row.error_message = "failed", str(e)
            await db.commit()
            return
        except anthropic.AnthropicError:
            logger.exception("Anthropic API call failed during document context extraction")
            row.status, row.error_message = "failed", AI_UNAVAILABLE_MESSAGE
            await db.commit()
            return
        except Exception:
            logger.exception("Unexpected failure during document context extraction")
            row.status, row.error_message = "failed", "Something went wrong while reading this document. Please try again."
            await db.commit()
            return

        row.document_text = document_text
        row.extracted_context = context.model_dump()
        row.status = "extracted"
        await db.commit()


async def _run_assessment(assessment_id: str, context: ExtractedContext):
    async with SessionLocal() as db:
        row = await db.get(DocumentAssessment, assessment_id)
        if not row:
            return
        try:
            generated = await run_in_threadpool(
                generate_document_assessment, row.document_title, row.document_text, context,
            )
        except ValueError as e:
            row.status, row.error_message = "failed", str(e)
            await db.commit()
            return
        except anthropic.AnthropicError:
            logger.exception("Anthropic API call failed during document assessment")
            row.status, row.error_message = "failed", AI_UNAVAILABLE_MESSAGE
            await db.commit()
            return
        except Exception:
            logger.exception("Unexpected failure during document assessment")
            row.status, row.error_message = "failed", "Something went wrong while assessing this document. Please try again."
            await db.commit()
            return

        result_dict = generated.model_dump()
        try:
            docx_path = await run_in_threadpool(
                render_document_assessment_docx,
                assessment_id=row.id, document_title=row.document_title, original_filename=row.original_filename,
                result=result_dict, context=context.model_dump(),
            )
        except Exception:
            logger.exception("Failed to render the document assessment .docx")
            row.status, row.error_message = "failed", "Something went wrong while generating the report. Please try again."
            await db.commit()
            return

        row.result = result_dict
        row.docx_file_path = docx_path
        row.status = "assessed"
        await db.commit()


@router.post("/extract", response_model=DocumentAssessmentOut, status_code=202)
async def extract_document_assessment(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_title: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large. Maximum size is 15MB.")

    title = document_title.strip() or Path(file.filename or "Document").stem

    assessment_id = uuid.uuid4().hex[:16]
    assessment_dir = DOCS_DIR / assessment_id
    assessment_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"original{ext}"
    file_path = assessment_dir / stored_name
    file_path.write_bytes(contents)

    row = DocumentAssessment(
        id=assessment_id,
        document_title=title,
        original_filename=file.filename or stored_name,
        file_path=str(file_path),
        status="extracting",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    background_tasks.add_task(_run_extraction, assessment_id, contents, file.filename or "", title)

    return _row_to_out(row)


@router.post("/{assessment_id}/assess", response_model=DocumentAssessmentOut, status_code=202)
async def assess_document(
    assessment_id: str, payload: AssessFromContextRequest,
    background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db),
):
    row = await db.get(DocumentAssessment, assessment_id)
    if not row:
        raise HTTPException(404, "Document assessment not found.")

    row.corrected_context = payload.context.model_dump()
    row.status = "assessing"
    row.error_message = ""
    await db.commit()
    await db.refresh(row)

    background_tasks.add_task(_run_assessment, assessment_id, payload.context)

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
