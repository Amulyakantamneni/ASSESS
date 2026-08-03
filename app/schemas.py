# app/schemas.py
# Pydantic request/response models. The Question/Score/Report shapes here are
# also used as the Claude structured-output schema (output_config.format).

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


class AssessmentResultOut(BaseModel):
    assessment_id: str
    template_name: str
    industry_name: str
    standard_name: str
    tier: str
    score: ScoreOut | None
    report: ReportOut | None


class ExplainScoreRequest(BaseModel):
    category: str


class ExplainScoreResponse(BaseModel):
    explanation: str


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
