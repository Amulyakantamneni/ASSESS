# app/ai/question_generator.py

from app.ai.claude_client import generate_structured
from app.ai.prompt_templates import question_generation_prompt
from app.schemas import GeneratedQuestionSet


def generate_questions(industry: str, standard: str, template_name: str, num_categories: int = 8) -> GeneratedQuestionSet:
    system, user = question_generation_prompt(industry, standard, template_name, num_categories)
    return generate_structured(system=system, user=user, schema_model=GeneratedQuestionSet, max_tokens=4096)
