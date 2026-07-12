"""
services/reasoning_report_generator.py

Reasoning grading + report -- single Gemini call does both judging and
narrating, unlike the MCQ two-stage pipeline (see module docstring in
the original CLI version for full reasoning).
"""

from google import genai
from app.services.gemini_utils import call_gemini_with_retry
from app.gemini_client import MODEL_NAME


class ReasoningReportGenerator:
    def __init__(self, client: genai.Client, model: str = MODEL_NAME):
        self.client = client
        self.model = model

    def generate_report(self, results: list[dict], grade: int = 9, subject: str = "Physics") -> str:
        qa_context = "\n\n".join(
            f"Question ({r['topic']}): {r['question']}\n"
            f"Model Answer: {r['model_answer']}\n"
            f"Student's Answer: {r['student_answer']}"
            for r in results
        )

        prompt = f"""
You are an expert grade {grade} {subject} teacher (Sindh Board of Secondary
Education syllabus). Grade the student's reasoning answers below by
comparing each one to its model answer. Judge based on conceptual
understanding, not exact wording -- partial credit is allowed.

{qa_context}

Write a markdown progress report suitable for emailing to a parent/student.
Include:
1. A heading with an overall qualitative assessment (Strong / Good / Needs
   Improvement) -- do not fabricate a numeric score.
2. Per-question evaluation: Correct / Partially Correct / Incorrect + feedback.
3. Topic-wise strengths and weaknesses.
4. A "Suggestions for Improvement" section.
5. A brief encouraging closing note.

Do not use emojis. Be honest but constructive.
"""

        response = call_gemini_with_retry(
            lambda: self.client.models.generate_content(model=self.model, contents=prompt)
        )
        return response.text
