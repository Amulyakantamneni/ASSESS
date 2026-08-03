# app/ai/scoring_engine.py

from app.ai.claude_client import generate_structured
from app.ai.prompt_templates import scoring_prompt
from app.schemas import GeneratedScorecard


def generate_scorecard(industry: str, standard: str, template_name: str, qa_pairs: list[dict]) -> GeneratedScorecard:
    system, user = scoring_prompt(industry, standard, template_name, qa_pairs)
    return generate_structured(system=system, user=user, schema_model=GeneratedScorecard, max_tokens=4096)
