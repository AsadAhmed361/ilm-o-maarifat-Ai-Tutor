"""
services/reasoning_question_generator.py

Reasoning question generation -- reused from the original CLI project.
"""

from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from app.services.gemini_utils import call_gemini_with_retry
from app.gemini_client import MODEL_NAME

class ReasoningQuestion(BaseModel):
    question: str = Field(description="An open-ended reasoning/short-answer question")
    topic: str = Field(description="Topic within the subject")
    model_answer: str = Field(description="The ideal reference answer, used later to judge the student's response")


class ReasoningQuestionSet(BaseModel):
    questions: list[ReasoningQuestion]


class ReasoningQuestionGenerator:
    def __init__(self, client: genai.Client, model: str = MODEL_NAME):
        self.client = client
        self.model = model

    def generate(self, num_questions: int = 5, grade: int = 9, subject: str = "Physics") -> list[dict]:
        prompt = (
            f"Generate {num_questions} open-ended reasoning/short-answer questions "
            f"for grade {grade} {subject}, following the Sindh Board of Secondary "
            "Education (Pakistan) syllabus. These should require the student to "
            "explain concepts in their own words, not just recall facts. "
            "For each question, provide a clear model answer that represents "
            "a strong, correct response -- this will be used later to judge "
            "student answers."
        )

        response = call_gemini_with_retry(
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ReasoningQuestionSet,
                ),
            )
        )

        parsed: ReasoningQuestionSet = response.parsed
        return [q.model_dump() for q in parsed.questions]
