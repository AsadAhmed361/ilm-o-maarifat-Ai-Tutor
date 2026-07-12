"""
services/question_generator.py

MCQ question generation -- reused from the original CLI project,
adapted for the API's import structure.
"""

import json
from typing import Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from app.services.gemini_utils import call_gemini_with_retry
from app.gemini_client import MODEL_NAME


class MCQQuestion(BaseModel):
    question: str = Field(description="The question text")
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: Literal["A", "B", "C", "D"]
    topic: str = Field(description="Topic within the subject")


class QuestionSet(BaseModel):
    questions: list[MCQQuestion]


class QuestionGenerator:
    def __init__(self, client: genai.Client, model: str = MODEL_NAME):
        self.client = client
        self.model = model

    def generate(self, num_questions: int = 10, grade: int = 9, subject: str = "Physics") -> list[dict]:
        prompt = (
            f"Generate {num_questions} multiple choice questions for grade {grade} "
            f"{subject}, following the Sindh Board of Secondary Education "
            "(Pakistan) syllabus. "
            f"Cover a mix of topics relevant to grade {grade} {subject}. "
            "Each question must have exactly one correct option. "
            f"Keep questions clear and appropriate for a grade {grade} student."
        )

        response = call_gemini_with_retry(
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=QuestionSet,
                ),
            )
        )

        parsed: QuestionSet = response.parsed
        return [q.model_dump() for q in parsed.questions]
