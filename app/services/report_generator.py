"""
services/report_generator.py

MCQ markdown report generation -- narrates already-graded facts, does
not calculate anything itself.
"""

from google import genai
from app.services.gemini_utils import call_gemini_with_retry


class ReportGenerator:
    def __init__(self, client: genai.Client, model: str = "gemini-2.5-flash"):
        self.client = client
        self.model = model

    def generate_markdown_report(self, report: dict, grade: int = 9, subject: str = "Physics") -> str:
        wrong_answers_context = "\n".join(
            f"- Topic: {g['topic']} | Question: {g['question']} | "
            f"Student answered: {g['student_answer']} | Correct answer: {g['correct_option']}"
            for g in report["graded_questions"] if not g["is_correct"]
        ) or "None -- student got everything correct."

        topic_summary = "\n".join(
            f"- {topic}: {stats['correct']}/{stats['total']} correct"
            for topic, stats in report["topic_breakdown"].items()
        )

        prompt = f"""
You are writing a progress report for a grade {grade} {subject} student
(Sindh Board of Secondary Education syllabus). Use ONLY the facts given
below -- do not invent or recalculate any numbers.

FACTS:
- Score: {report['total_score']}/{report['total_questions']} ({report['percentage']}%)
- Topic-wise performance:
{topic_summary}

- Questions answered incorrectly:
{wrong_answers_context}

Write a clear, encouraging, and honest progress report in MARKDOWN format
suitable for emailing to a parent/student. Include:
1. A heading with the overall score
2. A short summary paragraph
3. A topic-wise performance table
4. A "Weak Areas & Suggestions" section based on incorrect answers
5. A brief encouraging closing note

Do not use emojis. Keep it professional and concise.
"""

        response = call_gemini_with_retry(
            lambda: self.client.models.generate_content(model=self.model, contents=prompt)
        )
        return response.text
