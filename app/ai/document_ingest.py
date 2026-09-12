# app/ai/document_ingest.py
# Turns an uploaded .pdf/.docx/.txt into plain text tagged with source
# citations — [Page N] for PDFs (native or OCR), [Section: ...] for DOCX
# (no native page concept pre-render) — so later Claude calls can cite where
# a finding came from. Also the one place file-level validation happens:
# password-protected/corrupt/empty documents are rejected here with a clear
# message rather than silently producing an empty or garbage assessment.

import io
import shutil

from pypdf import PdfReader
from docx import Document as DocxDocument
from docx.text.paragraph import Paragraph
from docx.table import Table

MIN_NATIVE_TEXT_CHARS = 20  # below this, treat a PDF page as likely scanned/image-only
MAX_DOCUMENT_CHARS = 150_000

_OCR_AVAILABLE = shutil.which("tesseract") is not None


def _ocr_pdf_page(contents: bytes, page_number: int) -> str:
    """OCRs a single 1-indexed PDF page. Returns '' if OCR isn't available
    locally (tesseract/poppler aren't installed) rather than raising, so
    dev environments without those system packages degrade gracefully."""
    if not _OCR_AVAILABLE:
        return ""
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError:
        return ""
    try:
        images = convert_from_bytes(contents, first_page=page_number, last_page=page_number)
        return pytesseract.image_to_string(images[0]) if images else ""
    except Exception:
        return ""


def _extract_pdf(contents: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(contents))
    except Exception:
        raise ValueError("This PDF appears to be corrupted or unreadable. Please try another file.")

    if reader.is_encrypted:
        result = reader.decrypt("")
        if not result:
            raise ValueError(
                "This PDF is password-protected and can't be read automatically. "
                "Please remove the password, or use the manual assessment instead."
            )

    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if len(text) < MIN_NATIVE_TEXT_CHARS:
            ocr_text = _ocr_pdf_page(contents, i).strip()
            if ocr_text:
                pages.append(f"[Page {i} - OCR]\n{ocr_text}")
                continue
        pages.append(f"[Page {i}]\n{text}")
    return "\n\n".join(pages)


def _extract_docx(contents: bytes) -> str:
    doc = DocxDocument(io.BytesIO(contents))
    lines = []
    current_section = None
    for block in doc.iter_inner_content():
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
            if block.style.name.startswith("Heading"):
                current_section = text
                lines.append(f"[Section: {current_section}]")
            else:
                lines.append(text)
        elif isinstance(block, Table):
            for row in block.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_document_text(contents: bytes, filename: str) -> str:
    """Extracts source-tagged plain text from an uploaded .pdf/.docx/.txt
    file. Raises ValueError (safe to surface directly to the user) on an
    unsupported, unreadable, encrypted, or effectively empty file."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "txt":
        text = contents.decode("utf-8", errors="ignore")
    elif ext == "docx":
        text = _extract_docx(contents)
    elif ext == "pdf":
        text = _extract_pdf(contents)
    else:
        raise ValueError(f"Unsupported file type: .{ext}")

    text = text.strip()
    if not text:
        raise ValueError(
            "No readable text could be extracted from this file, even with OCR. "
            "This document can't be reliably assessed — please try another file, "
            "or use the manual assessment instead."
        )

    if len(text) > MAX_DOCUMENT_CHARS:
        text = text[:MAX_DOCUMENT_CHARS] + "\n\n[Document truncated for length.]"

    return text
