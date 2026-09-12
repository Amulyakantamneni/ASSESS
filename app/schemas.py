# app/schemas.py
# Pydantic request/response models. The Question/Score/Report shapes here are
# also used as the Claude structured-output schema (output_config.format).

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, EmailStr


class StrictModel(BaseModel):
    """Base for schemas sent to Claude as output_config.format — additionalProperties:false is required."""
    model_config = ConfigDict(extra="forbid")


# ---------- Industries / Standards / Templates ----------

class IndustryOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str


class StandardOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str


class TemplateOut(BaseModel):
    id: str
    name: str
    description: str


# ---------- AI-generated questions ----------

QuestionType = Literal["multiple_choice", "yes_no", "rating_scale", "evidence", "text"]


class QuestionOption(StrictModel):
    value: int
    label: str


class GeneratedQuestion(StrictModel):
    category: str
    question_text: str
    question_type: QuestionType
    options: list[QuestionOption] = Field(default_factory=list)


class GeneratedQuestionSet(StrictModel):
    questions: list[GeneratedQuestion]


class QuestionOut(BaseModel):
    id: str
    category: str
    question_text: str
    question_type: QuestionType
    options: list[QuestionOption] = Field(default_factory=list)


# ---------- Assessment flow ----------

class StartAssessmentRequest(BaseModel):
    template_id: str
    tier: Literal["free", "premium"] = "free"
    email: EmailStr | None = None


class StartAssessmentResponse(BaseModel):
    assessment_id: str
    tier: str
    questions: list[QuestionOut]


class AnswerIn(BaseModel):
    question_id: str
    answer: dict
    evidence_note: str = ""


class SubmitAssessmentRequest(BaseModel):
    email: EmailStr | None = None
    responses: list[AnswerIn]


# ---------- Scoring (also the Claude structured-output schema) ----------

class CategoryScore(StrictModel):
    category: str
    score: float
    gap: float
    insight: str
    recommendation: str


class GeneratedScorecard(StrictModel):
    overall_score: float
    maturity_level: str
    compliance_pct: float
    risk_rating: Literal["low", "medium", "high", "critical"]
    strengths: list[str]
    gaps: list[str]
    category_scores: list[CategoryScore]


# ---------- Report (also the Claude structured-output schema) ----------

class RoadmapItem(StrictModel):
    action: str
    rationale: str


class Roadmap(StrictModel):
    day_30: list[RoadmapItem]
    day_60: list[RoadmapItem]
    day_90: list[RoadmapItem]


class GeneratedReport(StrictModel):
    executive_summary: str
    current_state: str
    missing_requirements: list[str]
    compliance_gaps: list[str]
    roadmap: Roadmap
    conclusion: str


class ScoreOut(BaseModel):
    overall_score: float
    maturity_level: str
    compliance_pct: float
    risk_rating: str
    strengths: list[str]
    gaps: list[str]
    category_scores: list[CategoryScore]


class ReportOut(BaseModel):
    executive_summary: str
    current_state: str
    missing_requirements: list[str]
    compliance_gaps: list[str]
    roadmap: Roadmap
    conclusion: str


class ResponseDetail(BaseModel):
    category: str
    question_text: str
    question_type: str
    answer: dict
    evidence_note: str = ""


class AssessmentResultOut(BaseModel):
    assessment_id: str
    template_name: str
    industry_name: str
    standard_name: str
    standard_id: str
    tier: str
    completed_at: datetime | None = None
    score: ScoreOut | None
    report: ReportOut | None
    responses: list[ResponseDetail] = Field(default_factory=list)


class ExplainScoreRequest(BaseModel):
    category: str


class ExplainScoreResponse(BaseModel):
    explanation: str


# ---------- Evidence ----------

class EvidenceOut(BaseModel):
    id: str
    assessment_id: str
    category: str
    file_name: str
    content_type: str
    status: str
    description: str
    uploaded_at: datetime


# ---------- Assessment history ----------

class AssessmentSummaryOut(BaseModel):
    assessment_id: str
    template_name: str
    industry_name: str
    standard_name: str
    standard_id: str
    tier: str
    completed_at: datetime | None
    overall_score: float | None
    maturity_level: str | None
    gap_count: int


class AssessmentHistoryOut(BaseModel):
    ok: bool = True
    assessments: list[AssessmentSummaryOut]


# ---------- Framework crosswalk ----------

class CrosswalkEntry(BaseModel):
    mapped_standard_name: str
    coverage_pct: float | None


class CrosswalkOut(BaseModel):
    available: bool
    standard_name: str
    mappings: list[CrosswalkEntry] = Field(default_factory=list)


# ---------- Controlled Document Maturity Assessment ----------
# Standalone flow: upload a document, score it against a fixed 15-category
# rubric. Unrelated to the Industry/Standard/Template questionnaire above.
# Two-phase pipeline: extract context (below) -> user reviews/corrects it ->
# assess (further below) using that context as grounding.

DocumentPriority = Literal["High", "Medium", "Low"]
DocumentConfidence = Literal["High", "Medium", "Low"]
GapPriority = Literal["Critical", "High", "Medium", "Low"]
ComplianceStatus = Literal[
    "Mentioned", "Applicable", "Addressed", "Partially Addressed",
    "Evidenced", "Not Evidenced", "Gap Identified",
]


# ---------- Phase 1: extracted context (reviewed/correctable by the user) ----------
# Deliberately flat (one level of nesting, only where a real table is needed)
# rather than a deep tree of small sub-models — a first version with 10 nested
# sub-models made the structured-output schema too large for Claude's strict
# JSON-schema grammar ("The compiled grammar is too large... reduce the number
# of strict tools"). Flattening to top-level string fields plus a single
# nested list (compliance_profile) keeps it well under that ceiling.

class ComplianceItem(StrictModel):
    requirement: str
    req_type: str
    applicability: str
    evidence: str
    status: ComplianceStatus
    source: str


class ExtractedContext(StrictModel):
    organization_name: str
    business_unit: str
    department: str
    function: str
    location: str
    organization_notes: str

    industry: str
    sub_industry: str
    business_model: str
    operating_environment: str
    industry_notes: str

    process_name: str
    process_purpose: str
    process_scope: str
    process_boundaries: str
    process_inputs: str
    process_outputs: str
    process_activities: str
    process_owner: str

    governance_roles: str
    governance_responsibilities: str
    governance_authority: str
    governance_approvals: str
    governance_escalation: str

    controls: list[str]
    risks: list[str]
    kpis: list[str]
    performance_targets: str
    performance_slas: str
    systems: list[str]
    automation_notes: str

    document_title: str
    document_number: str
    document_version: str
    document_owner: str
    document_author: str
    document_approver: str
    effective_date: str
    review_date: str
    classification: str

    compliance_profile: list[ComplianceItem]


# ---------- Phase 2: evidence-based maturity assessment ----------

class DocumentCategoryScore(StrictModel):
    # Kept lean (no nested string-list fields) — combined with GapItem and
    # DocumentImprovementRecommendation below in one schema, adding per-item
    # array fields here pushed Claude's structured-output schema over its
    # compiled grammar size limit ("reduce the number of strict tools"),
    # discovered empirically. strengths_and_risks folds what would have been
    # two separate list[str] fields into one field.
    category: str
    score: int
    confidence: DocumentConfidence
    source: str
    evidence_found: str
    gaps_identified: str
    strengths_and_risks: str
    recommendation: str


class GapItem(StrictModel):
    gap_id: str
    category: str
    requirement: str
    gap_detail: str  # current state vs. expected state vs. evidence, combined
    source: str
    impact: str  # risk / business / compliance / maturity impact, combined
    priority: GapPriority


class DocumentImprovementRecommendation(StrictModel):
    recommendation: str
    business_benefit: str
    risk_if_not_addressed: str
    priority: DocumentPriority
    estimated_maturity_gain: str
    quick_win: bool
    evidence_basis: str  # finding, related gap, complexity, owner, dependencies, combined


class GeneratedDocumentAssessment(StrictModel):
    # Ordered so the most important structured content (category scores, gap
    # analysis, recommendations) is generated before the more verbose
    # narrative fields — if a very long document ever pushes the response
    # toward the token ceiling, it's the narrative prose that gets cut short,
    # not the structured content the rest of the report depends on.
    #
    # Kept to only 2 nested list-of-object types (DocumentCategoryScore,
    # DocumentImprovementRecommendation) plus GapItem — combining more than
    # that pushed Claude's strict structured-output schema over its compiled
    # grammar size limit ("reduce the number of strict tools"), discovered
    # empirically when DocumentRoadmap/RoadmapItem was a 4th/5th nested type.
    # The roadmap is therefore flat lists of "Action: Rationale" strings.
    overall_maturity_score: float
    overall_maturity_level: str
    category_scores: list[DocumentCategoryScore]
    gap_analysis: list[GapItem]
    top_recommendations: list[DocumentImprovementRecommendation]
    highest_scoring_areas: list[str]
    lowest_scoring_areas: list[str]
    key_strengths: list[str]
    key_weaknesses: list[str]
    overall_assessment: str
    evidence_coverage_pct: float
    compliance_readiness_pct: float
    assessment_confidence: DocumentConfidence
    current_maturity_level: str
    target_maturity_level: str
    roadmap_day_30: list[str]
    roadmap_day_60: list[str]
    roadmap_day_90: list[str]
    roadmap_beyond_90: list[str]
    overall_readiness_pct: float


# ---------- API request/response shapes ----------

class AssessFromContextRequest(BaseModel):
    context: ExtractedContext


class DocumentAssessmentOut(BaseModel):
    id: str
    document_title: str
    original_filename: str
    created_at: datetime
    status: str
    extracted_context: ExtractedContext | None = None
    result: GeneratedDocumentAssessment | None = None


# ---------- Leads ----------

class LeadIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    company: str = Field(default="", max_length=200)
    message: str = Field(default="", max_length=2000)
    source: str = "unknown"


class LeadOut(BaseModel):
    id: str
    name: str
    email: str
    company: str
    message: str
    source: str
    created_at: str


# ---------- Admin ----------

class AdminLoginRequest(BaseModel):
    username: str
    password: str


class IndustryIn(BaseModel):
    name: str
    slug: str
    description: str = ""


class StandardIn(BaseModel):
    industry_id: str
    name: str
    slug: str
    description: str = ""


class TemplateIn(BaseModel):
    standard_id: str
    name: str
    description: str = ""


class QuestionIn(BaseModel):
    template_id: str
    category: str
    question_text: str
    question_type: QuestionType
    options: list[QuestionOption] = Field(default_factory=list)
    order_index: int = 0
