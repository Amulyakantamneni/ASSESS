# app/db/models.py
# SQLAlchemy ORM models. Uses the generic JSON type (not JSONB) so the same
# models work against both SQLite (local dev) and Postgres (production).

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Industry(Base):
    __tablename__ = "industries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    standards: Mapped[list["Standard"]] = relationship(back_populates="industry", cascade="all, delete-orphan")


class Standard(Base):
    __tablename__ = "standards"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    industry_id: Mapped[str] = mapped_column(ForeignKey("industries.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    industry: Mapped["Industry"] = relationship(back_populates="standards")
    templates: Mapped[list["AssessmentTemplate"]] = relationship(back_populates="standard", cascade="all, delete-orphan")


class AssessmentTemplate(Base):
    __tablename__ = "assessment_templates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    standard_id: Mapped[str] = mapped_column(ForeignKey("standards.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    standard: Mapped["Standard"] = relationship(back_populates="templates")
    questions: Mapped[list["Question"]] = relationship(back_populates="template", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    template_id: Mapped[str] = mapped_column(ForeignKey("assessment_templates.id"), nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String, nullable=False)  # multiple_choice|yes_no|rating_scale|evidence|text
    options: Mapped[list | None] = mapped_column(JSON, default=list)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    template: Mapped["AssessmentTemplate"] = relationship(back_populates="questions")


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    template_id: Mapped[str] = mapped_column(ForeignKey("assessment_templates.id"), nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    tier: Mapped[str] = mapped_column(String, default="free")  # free|premium
    status: Mapped[str] = mapped_column(String, default="in_progress")  # in_progress|completed
    questions_snapshot: Mapped[list | None] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    template: Mapped["AssessmentTemplate"] = relationship()
    responses: Mapped[list["Response"]] = relationship(back_populates="assessment", cascade="all, delete-orphan")
    score: Mapped["Score"] = relationship(back_populates="assessment", uselist=False, cascade="all, delete-orphan")
    report: Mapped["Report"] = relationship(back_populates="assessment", uselist=False, cascade="all, delete-orphan")
    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="assessment", cascade="all, delete-orphan")


class Response(Base):
    __tablename__ = "responses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), nullable=False)
    question_id: Mapped[str] = mapped_column(String, nullable=False)
    answer: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_note: Mapped[str] = mapped_column(Text, default="")

    assessment: Mapped["Assessment"] = relationship(back_populates="responses")


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), nullable=False, unique=True)
    overall_score: Mapped[float] = mapped_column(Float, default=0)
    maturity_level: Mapped[str] = mapped_column(String, default="")
    compliance_pct: Mapped[float] = mapped_column(Float, default=0)
    risk_rating: Mapped[str] = mapped_column(String, default="")
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    category_scores: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assessment: Mapped["Assessment"] = relationship(back_populates="score")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), nullable=False, unique=True)
    executive_summary: Mapped[str] = mapped_column(Text, default="")
    detailed_analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    roadmap_30_60_90: Mapped[dict] = mapped_column(JSON, default=dict)
    docx_file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assessment: Mapped["Assessment"] = relationship(back_populates="report")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="self_reported")  # self_reported|partial|verified
    description: Mapped[str] = mapped_column(Text, default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assessment: Mapped["Assessment"] = relationship(back_populates="evidence_items")


class FrameworkCrosswalk(Base):
    """Cross-framework requirement mapping. Intentionally unpopulated: no seed data
    inserts rows here today. Its existence lets the crosswalk endpoint return a real
    'unavailable' response instead of an ad hoc 404, and gives the architecture a home
    for real mappings if they're ever added, without inventing coverage numbers now."""
    __tablename__ = "framework_crosswalks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    standard_id: Mapped[str] = mapped_column(ForeignKey("standards.id"), nullable=False)
    mapped_standard_id: Mapped[str] = mapped_column(ForeignKey("standards.id"), nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    mapped_category: Mapped[str | None] = mapped_column(String, nullable=True)
    coverage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DocumentAssessment(Base):
    """A standalone controlled-document maturity assessment: upload a procedure,
    policy, or similar document and get it scored against the fixed 15-category
    rubric directly, with no questionnaire involved. Unrelated to the
    Industry/Standard/Template/Assessment flow above."""
    __tablename__ = "document_assessments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    document_title: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    docx_file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, default="")
    message: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String, default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiReportUsage(Base):
    __tablename__ = "ai_report_usage"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String, nullable=False)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
