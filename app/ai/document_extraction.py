# app/ai/document_extraction.py
# Phase 1 of the document assessment pipeline: reads the document and extracts
# organizational/industry/process/governance/compliance context — no scoring
# yet. This is what the user reviews and can correct before Phase 2 (scoring,
# in app/ai/document_maturity.py) runs against it.

import pydantic

from app.ai.claude_client import generate_structured
from app.ai.prompt_templates import STYLE_DIRECTIVE
from app.schemas import ExtractedContext

NOT_A_CONTROLLED_DOCUMENT_MESSAGE = (
    "This document doesn't appear to contain the kind of organizational, process, "
    "or governance content this assessment evaluates. Please upload a procedure, "
    "policy, manual, standard, or similar controlled document."
)


def _is_effectively_empty(context: ExtractedContext) -> bool:
    """True when extraction came back with essentially nothing usable — the
    document was readable but isn't the kind of controlled document this
    assessment is for (e.g. a resume, invoice, or unrelated text)."""
    signal_fields = [
        context.organization_name, context.function, context.process_name,
        context.process_purpose, context.governance_roles, context.document_title,
    ]
    signal_lists = [context.controls, context.risks, context.compliance_profile]
    return not any(f.strip() for f in signal_fields) and not any(signal_lists)

EXTRACTION_SYSTEM_PROMPT = (
    "You are a management-systems analyst preparing a document for an audit-grade "
    "maturity assessment. Your only job right now is extraction, not scoring: read "
    "the document and pull out its real organizational, industry, process, "
    "governance, and compliance context.\n\n"
    "Only report what the document actually contains or clearly implies. Where a "
    "field genuinely isn't covered by the document, return an empty string (or "
    "empty list) rather than inventing plausible-sounding content — a blank field "
    "is honest, a guessed one is not. Mentioning a regulation, standard, or "
    "certification is not the same as the document proving compliance with it: "
    "classify each compliance_profile entry's status carefully (Mentioned, "
    "Applicable, Addressed, Partially Addressed, Evidenced, Not Evidenced, or Gap "
    "Identified) rather than defaulting everything to 'Addressed'.\n\n"
    "Wherever you can identify where something came from, put a short citation in "
    "that item's source field (e.g. 'Page 7' for a PDF page-tagged source, or "
    "'Section: Roles and Responsibilities' for a DOCX section-tagged source) — the "
    "document text you're given is pre-tagged with [Page N] or [Section: ...] "
    "markers for exactly this purpose. " + STYLE_DIRECTIVE
)


def extract_context(document_title: str, tagged_text: str) -> ExtractedContext:
    user = (
        f"Document title: {document_title}\n\n"
        f"Extract:\n"
        f"- organization_name, business_unit, department, function, location, organization_notes\n"
        f"- industry, sub_industry, business_model, operating_environment, industry_notes\n"
        f"- process_name, process_purpose, process_scope, process_boundaries, process_inputs, "
        f"process_outputs, process_activities, process_owner\n"
        f"- governance_roles, governance_responsibilities, governance_authority, "
        f"governance_approvals, governance_escalation\n"
        f"- controls: a list of short descriptions of preventive/detective controls (name, type, "
        f"owner, frequency folded into one descriptive line each)\n"
        f"- risks: a list of short descriptions (risk, category, mitigation, escalation folded "
        f"into one descriptive line each)\n"
        f"- kpis: a list, performance_targets, performance_slas\n"
        f"- systems: a list, automation_notes\n"
        f"- document_title, document_number, document_version, document_owner, document_author, "
        f"document_approver, effective_date, review_date, classification\n"
        f"- compliance_profile: every legislation/regulation/regulatory body/ISO or "
        f"industry standard/certification/framework/contractual or internal policy "
        f"requirement the document references, each with requirement, req_type, "
        f"applicability, evidence, status, source\n\n"
        f"Document text (tagged with [Page N] or [Section: ...] source markers):\n\n"
        f"{tagged_text}"
    )

    context = None
    for _ in range(2):  # one retry against a transient malformed/incomplete response
        try:
            context = generate_structured(
                system=EXTRACTION_SYSTEM_PROMPT, user=user, schema_model=ExtractedContext,
                max_tokens=16000, stream=True,
            )
            break
        except pydantic.ValidationError:
            continue
    if context is None:
        raise ValueError("Could not process this document. Please try again.")

    if _is_effectively_empty(context):
        raise ValueError(NOT_A_CONTROLLED_DOCUMENT_MESSAGE)

    return context
