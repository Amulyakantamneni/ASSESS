# app/ai/document_maturity.py
# Phase 2 of the document assessment pipeline: scores an uploaded procedure,
# policy, or similar governance document against a fixed 15-category rubric,
# grounded in the (possibly user-corrected) context from Phase 1
# (app/ai/document_extraction.py). Standalone from the Industry/Standard/
# Template questionnaire flow elsewhere in app/ai.

import pydantic

from app.ai.claude_client import generate_structured
from app.ai.prompt_templates import STYLE_DIRECTIVE
from app.schemas import ExtractedContext, GeneratedDocumentAssessment

# The 15 fixed evaluation categories, each with the assessment bullets from the
# source rubric. Fixed and ordered so every assessment covers exactly these
# categories, in this order, rather than leaving category selection to Claude.
DOCUMENT_MATURITY_CATEGORIES: list[dict] = [
    {
        "name": "Strategic Alignment",
        "assess": (
            "Alignment with organizational strategy, business objectives, corporate "
            "policies, governance requirements, and regulatory obligations. Whether "
            "clear links are established, purpose is explained, and business value "
            "is evident."
        ),
    },
    {
        "name": "Purpose and Scope",
        "assess": (
            "Clarity of purpose, scope completeness, boundaries defined, inclusions "
            "and exclusions defined, applicability specified."
        ),
    },
    {
        "name": "Process Definition",
        "assess": (
            "Whether the process is described logically, workflow clarity, inputs "
            "identified, outputs identified, activities described, sequence "
            "understandable — whether a new employee could execute the process "
            "successfully using only this document."
        ),
    },
    {
        "name": "Roles and Responsibilities",
        "assess": (
            "Ownership defined, accountability defined, authorities defined, "
            "escalation paths defined, delegation rules defined, whether RACI "
            "principles are evident, and whether ambiguity exists."
        ),
    },
    {
        "name": "Controls and Governance",
        "assess": (
            "Approval requirements, review requirements, monitoring activities, "
            "compliance requirements, management oversight, and the overall "
            "robustness of governance controls."
        ),
    },
    {
        "name": "Risk Integration",
        "assess": (
            "Whether the document addresses operational, compliance, safety, "
            "knowledge-loss, cybersecurity, and human-performance risks, and "
            "whether risk controls, mitigation measures, and escalation criteria "
            "are present."
        ),
    },
    {
        "name": "Document Control Maturity",
        "assess": (
            "Revision management, version control, approval records, review cycle, "
            "change control process, obsolete document controls, and alignment with "
            "documented-information requirements and document lifecycle controls."
        ),
    },
    {
        "name": "Process Performance Management",
        "assess": (
            "Presence of KPIs, targets, service levels, effectiveness measures, "
            "efficiency measures, and whether process success can be objectively "
            "measured."
        ),
    },
    {
        "name": "Knowledge Management",
        "assess": (
            "Lessons-learned integration, knowledge capture and sharing mechanisms, "
            "retention of critical knowledge, references to repositories, "
            "protection of knowledge, and vulnerability to knowledge loss."
        ),
    },
    {
        "name": "Human Factors and Usability",
        "assess": (
            "Readability, simplicity, logical structure, visual aids, process maps, "
            "flowcharts, tables, user friendliness, and whether the document "
            "supports human performance."
        ),
    },
    {
        "name": "Compliance Readiness",
        "assess": (
            "Regulatory alignment, standard alignment, internal requirements "
            "alignment, audit trail capability, evidence requirements, and audit "
            "readiness."
        ),
    },
    {
        "name": "Process Integration",
        "assess": (
            "How well the document integrates with related procedures, policies, "
            "manuals, systems, databases, and enterprise processes, and the degree "
            "of silo risk."
        ),
    },
    {
        "name": "Continuous Improvement Capability",
        "assess": (
            "Review triggers, feedback mechanisms, corrective actions, preventive "
            "actions, improvement opportunities, and whether continual improvement "
            "is embedded."
        ),
    },
    {
        "name": "Digital Readiness",
        "assess": (
            "Automation opportunities, workflow integration, system integration, AI "
            "enablement, data capture capability, and whether the process is future "
            "ready."
        ),
    },
    {
        "name": "Benchmark Against Industry Best Practice",
        "assess": (
            "Comparison against ISO management system practices, industry "
            "expectations, high reliability organizations, and world-class "
            "governance frameworks, and the resulting maturity gap."
        ),
    },
]

EVIDENCE_CLASSIFICATION = (
    "Classify every finding as Explicit Evidence (directly stated), Strong "
    "Indication (reasonably supported but not explicit), Not Evidenced "
    "(insufficient basis in the document), or External Benchmark (derived from "
    "an applicable external standard or best practice, not from the document "
    "itself). When there is no basis in the document, say exactly 'Not evidenced "
    "in the source document.' When comparing against an external requirement "
    "the document doesn't address, say exactly 'External benchmark requirement "
    "— not evidenced in the source document.' Never treat absence of evidence "
    "as evidence of absence — say the evidence is missing, don't assume the "
    "practice doesn't exist."
)


def _format_context(context: ExtractedContext) -> str:
    c = context
    lines = [
        f"Organization: {c.organization_name} | {c.business_unit} | {c.department} | "
        f"{c.function} | {c.location}",
        f"Industry: {c.industry} / {c.sub_industry} — {c.business_model} — {c.operating_environment}",
        f"Process: {c.process_name} — purpose: {c.process_purpose} — scope: {c.process_scope} — "
        f"owner: {c.process_owner}",
        f"Governance: roles={c.governance_roles} | approvals={c.governance_approvals} | "
        f"escalation={c.governance_escalation}",
        "Controls: " + "; ".join(c.controls),
        "Risks: " + "; ".join(c.risks),
        f"Performance: KPIs={', '.join(c.kpis)} | targets={c.performance_targets}",
        f"Technology: systems={', '.join(c.systems)}",
        f"Document control: {c.document_title} v{c.document_version}, owner {c.document_owner}, "
        f"effective {c.effective_date}",
        "Compliance profile: " + "; ".join(
            f"{item.requirement} [{item.status}]" for item in c.compliance_profile
        ),
    ]
    return "\n".join(lines)


def document_assessment_prompt(document_title: str, document_text: str, context: ExtractedContext) -> tuple[str, str]:
    category_list = "\n".join(
        f"{i + 1}. {c['name']} — assess: {c['assess']}"
        for i, c in enumerate(DOCUMENT_MATURITY_CATEGORIES)
    )

    system = (
        "Act as a Senior Management Systems Auditor, Governance Assessor, Process "
        "Excellence Consultant, ISO Lead Auditor, and Document Control Expert, with "
        "expertise in ISO 9001, ISO 30401, ISO 55001, ISO 37301, ISO 37000, APQC "
        "Process Management, BPMM (Business Process Maturity Model), Document "
        "Governance, Enterprise Risk Management, Asset Intensive Industry Management "
        "Systems, and High Reliability Organization (HRO) Practices.\n\n"
        "Your task is to perform a comprehensive, evidence-based maturity assessment "
        "of a controlled document (a procedure, process description, management "
        "system manual, governance framework, standard, work instruction, or "
        "guideline). You have already been given a reviewed extraction of the "
        "document's organizational, industry, process, governance, and compliance "
        "context — use it as ground truth rather than re-deriving it, but ground "
        "every score, evidence, gap, and recommendation in the actual document text "
        "you're given, not just the context summary. " + EVIDENCE_CLASSIFICATION + " "
        "Score every one of the 15 fixed categories below on this maturity scale: "
        "1 = Initial/Ad Hoc, 2 = Repeatable, 3 = Defined, 4 = Managed, "
        "5 = Optimized/Best Practice. Never default every category to the same "
        "middle score. " + STYLE_DIRECTIVE
    )

    user = (
        f"Document title: {document_title}\n\n"
        f"Reviewed context (corrected by the user where needed — treat as accurate):\n"
        f"{_format_context(context)}\n\n"
        f"Evaluate the document against exactly these 15 categories, in this order:\n"
        f"{category_list}\n\n"
        f"This is a full audit-grade assessment, not a summary — write it with the "
        f"depth of a consulting deliverable a client is paying for, not a checklist. "
        f"For each category, provide:\n"
        f"- score (1-5), confidence (High/Medium/Low, reflecting evidence quantity, "
        f"quality, clarity, and how much you had to infer), source (a short citation "
        f"using the document's [Page N] or [Section: ...] markers)\n"
        f"- evidence_found: a substantive paragraph (3-5 sentences) citing specific "
        f"content actually in the document that supports this score. If there's "
        f"genuinely little to cite, say so explicitly rather than padding.\n"
        f"- gaps_identified: a substantive paragraph (3-5 sentences) on what's "
        f"missing, weak, or ambiguous, specific to this document.\n"
        f"- strengths_and_risks: 2-4 sentences combining this category's specific "
        f"strengths and risks\n"
        f"- recommendation: a detailed, actionable paragraph (2-4 sentences)\n\n"
        f"Also provide:\n"
        f"- overall_maturity_score (average across categories) and overall_maturity_level\n"
        f"- highest_scoring_areas and lowest_scoring_areas (category names)\n"
        f"- key_strengths and key_weaknesses: 4-6 specific, detailed bullets each\n"
        f"- overall_assessment: 4-6 full paragraphs covering the document's overall "
        f"posture, biggest risks, comparison to a world-class version, and the "
        f"practical consequences of its current gaps\n"
        f"- gap_analysis: one entry for every category scoring 3 or below (skip "
        f"categories scoring 4-5, they have no material gap), each with a gap_id "
        f"(e.g. 'GAP-01'), category, requirement, gap_detail (current state vs. "
        f"expected state vs. evidence, combined into one substantive paragraph), "
        f"source, impact (risk / business / compliance / maturity impact, combined "
        f"into one paragraph), and priority (Critical/High/Medium/Low)\n"
        f"- exactly 10 top_recommendations ranked by priority, each with "
        f"recommendation, business_benefit, risk_if_not_addressed, priority, "
        f"estimated_maturity_gain, quick_win (true only if it takes under a month "
        f"and minimal effort), and evidence_basis (the specific finding that "
        f"motivated it, which gap_id it addresses if any, complexity, suggested "
        f"owner, and dependencies, combined into one substantive paragraph)\n"
        f"- evidence_coverage_pct (0-100, how much of the assessment is Explicit "
        f"Evidence or Strong Indication vs. Not Evidenced), compliance_readiness_pct "
        f"(0-100), assessment_confidence (High/Medium/Low overall)\n"
        f"- current_maturity_level and target_maturity_level (a full paragraph "
        f"describing what a Level 5 version of this specific document would contain)\n"
        f"- roadmap_day_30, roadmap_day_60, roadmap_day_90, roadmap_beyond_90: each a "
        f"list of concrete actions as '<Action>: <rationale tied to a specific gap>' "
        f"strings\n"
        f"- overall_readiness_pct (0-100)\n\n"
        f"Document text:\n\n{document_text}"
    )

    return system, user


def _is_complete(result: GeneratedDocumentAssessment) -> bool:
    return len(result.category_scores) >= len(DOCUMENT_MATURITY_CATEGORIES) and bool(result.top_recommendations)


def generate_document_assessment(
    document_title: str, document_text: str, context: ExtractedContext,
) -> GeneratedDocumentAssessment:
    system, user = document_assessment_prompt(document_title, document_text, context)

    for _ in range(2):  # one retry: this is a large generation and occasionally runs long or malformed
        try:
            result = generate_structured(
                system=system, user=user, schema_model=GeneratedDocumentAssessment, max_tokens=48000, stream=True,
            )
        except pydantic.ValidationError:
            continue
        if _is_complete(result):
            return result

    raise ValueError("Could not complete the assessment. Please try again.")
