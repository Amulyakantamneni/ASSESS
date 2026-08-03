# app/ai/prompt_templates.py
# Prompt-building functions, parameterized by industry/standard/template so
# behavior is data-driven rather than hardcoded per industry.

STYLE_DIRECTIVE = (
    "Writing style: write in plain, professional prose, the way a sharp human consultant "
    "would. Use complete sentences with normal punctuation (periods, commas, colons, "
    "semicolons). Never use em dashes or en dashes. Avoid generic AI-sounding phrasing "
    "and filler."
)


def question_generation_prompt(industry: str, standard: str, template_name: str, num_categories: int = 8) -> tuple[str, str]:
    system = (
        "You are a process-maturity and compliance assessment designer. "
        "You write assessment questionnaires that evaluate an organization's maturity "
        "against a named industry standard or framework. Questions must be concrete, "
        "answerable without specialist consulting help, and cover the standard's real "
        "requirement areas, not generic filler. "
        + STYLE_DIRECTIVE
    )
    user = (
        f"Design an assessment for:\n"
        f"Industry: {industry}\n"
        f"Standard/Framework: {standard}\n"
        f"Assessment name: {template_name}\n\n"
        f"Generate {num_categories} questions, one per distinct capability/requirement category "
        f"relevant to this standard. For each question, pick the question_type that best fits "
        f"what's being assessed:\n"
        f"- rating_scale: for maturity-style questions, with 5 options valued 1-5 from least to most mature\n"
        f"- yes_no: for binary compliance checks, with 2 options valued 1 (no) and 5 (yes)\n"
        f"- multiple_choice: for questions with a few distinct qualitative states, 3-5 options valued 1-5\n"
        f"- text: for open-ended questions needing a written answer (no options)\n"
        f"- evidence: for questions asking the user to describe supporting documentation (no options)\n\n"
        f"Category names should be specific to {standard} (real control or requirement domains), "
        f"not generic labels like 'Category 1'."
    )
    return system, user


def scoring_prompt(industry: str, standard: str, template_name: str, qa_pairs: list[dict]) -> tuple[str, str]:
    system = (
        "You are a senior compliance and process-maturity assessor. You analyze an "
        "organization's questionnaire responses and produce an honest, evidence-based "
        "scorecard against a named standard. Be specific and reference the actual answers "
        "given, not generic advice. Scores should reflect real signal in the answers, not "
        "default to the middle. "
        + STYLE_DIRECTIVE
    )
    qa_text = "\n".join(
        f"- [{qa['category']}] Q: {qa['question']}\n  A: {qa['answer']}" for qa in qa_pairs
    )
    user = (
        f"Industry: {industry}\nStandard/Framework: {standard}\nAssessment: {template_name}\n\n"
        f"Responses:\n{qa_text}\n\n"
        f"Produce a scorecard: overall_score (0-100), maturity_level (a short label such as "
        f"'Initial', 'Repeatable', 'Defined', 'Managed', 'Optimizing' or standard-appropriate "
        f"equivalent), compliance_pct (0-100, how much of {standard}'s requirements this "
        f"organization appears to satisfy), risk_rating, top strengths, top gaps, and a "
        f"per-category breakdown (score 0-5, gap 0-5, one-sentence insight, one-sentence "
        f"recommendation) for every category that appeared in the responses."
    )
    return system, user


def report_prompt(industry: str, standard: str, template_name: str, scorecard: dict) -> tuple[str, str]:
    system = (
        "You are a management consultant writing an executive assessment report. "
        "Write in clear, professional, plain language with no filler, no hedging, and no "
        "generic advice that could apply to any organization. Ground every claim in "
        "the scorecard data you were given. "
        + STYLE_DIRECTIVE
    )
    user = (
        f"Industry: {industry}\nStandard/Framework: {standard}\nAssessment: {template_name}\n\n"
        f"Scorecard:\n{scorecard}\n\n"
        f"Write a full report: executive_summary (2-3 paragraphs), current_state (1-2 "
        f"paragraphs describing where the organization stands today), missing_requirements "
        f"(list of specific gaps against {standard}), compliance_gaps (list), a roadmap with "
        f"concrete actions grouped into day_30 / day_60 / day_90 (each action has a rationale "
        f"tied to a specific gap), and a short conclusion."
    )
    return system, user


def explain_score_prompt(industry: str, standard: str, category: str, score: float, insight: str, recommendation: str) -> tuple[str, str]:
    system = (
        "You explain assessment scores to the person who took the assessment. Be direct, "
        "specific, and reference their actual score and category, not generic advice. "
        + STYLE_DIRECTIVE
    )
    user = (
        f"Industry: {industry}\nStandard/Framework: {standard}\n"
        f"Category: {category}\nScore: {score}/5\n"
        f"Existing insight: {insight}\nExisting recommendation: {recommendation}\n\n"
        f"In 2-3 sentences, explain in plain language why this category likely received this "
        f"score and what it means in practice for the organization."
    )
    return system, user
