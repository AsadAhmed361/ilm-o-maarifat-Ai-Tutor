"""
services/test_service.py

Shared business logic for creating and submitting tests. Used by BOTH
the REST /test endpoints AND the AI tutor's function-calling tools --
single source of truth, no duplicated grading/generation logic.

Raises plain Python exceptions (ValueError, LookupError), not
HTTPException -- this layer doesn't know about HTTP. Callers translate
exceptions into whatever error format their context needs.
"""

from sqlalchemy.orm import Session
from google import genai

from app import models
from app.services.question_generator import QuestionGenerator
from app.services.reasoning_question_generator import ReasoningQuestionGenerator
from app.services.grader import Grader
from app.services.report_generator import ReportGenerator
from app.services.reasoning_report_generator import ReasoningReportGenerator


def create_test_session(
    db: Session,
    user: models.User,
    grade: int,
    subject: str,
    test_type: str,
    client: genai.Client,
) -> tuple[models.TestSession, list[dict]]:
    if test_type not in ("mcq", "reasoning"):
        raise ValueError(f"Invalid test_type: {test_type}")

    session = models.TestSession(user_id=user.id, grade=grade, subject=subject, test_type=test_type)
    db.add(session)
    db.flush()

    if test_type == "mcq":
        generator = QuestionGenerator(client)
        raw_questions = generator.generate(num_questions=10, grade=grade, subject=subject)
    else:
        generator = ReasoningQuestionGenerator(client)
        raw_questions = generator.generate(num_questions=5, grade=grade, subject=subject)

    db_questions = []
    for q in raw_questions:
        db_question = models.TestQuestion(
            session_id=session.id,
            question=q["question"],
            topic=q["topic"],
            option_a=q.get("option_a"),
            option_b=q.get("option_b"),
            option_c=q.get("option_c"),
            option_d=q.get("option_d"),
            correct_option=q.get("correct_option"),
            model_answer=q.get("model_answer"),
        )
        db.add(db_question)
        db_questions.append(db_question)

    db.commit()
    db.refresh(session)
    for q in db_questions:
        db.refresh(q)

    # NEVER include correct_option/model_answer here -- this feeds into
    # BOTH the REST response and the AI tutor's tool response. Anything
    # here becomes part of the model's context and could leak back to
    # the student conversationally.
    safe_questions = [
        {
            "id": q.id,
            "question": q.question,
            "topic": q.topic,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
        }
        for q in db_questions
    ]

    return session, safe_questions


def submit_test_session(
    db: Session,
    user: models.User,
    session_id: int,
    answers: list[dict],
    client: genai.Client,
) -> tuple[models.TestSession, str, str]:
    session = (
        db.query(models.TestSession)
        .filter(models.TestSession.id == session_id, models.TestSession.user_id == user.id)
        .first()
    )
    if not session:
        raise LookupError(f"Test session {session_id} not found")

    if session.completed:
        raise ValueError("This test has already been submitted")

    answer_map = {a["question_id"]: a["student_answer"] for a in answers}
    questions = db.query(models.TestQuestion).filter(models.TestQuestion.session_id == session_id).all()

    matched_any = any(q.id in answer_map for q in questions)
    if not matched_any and len(answers) == len(questions):
        # Fallback: the caller (e.g. the AI tutor) may have used sequential
        # display numbers (1, 2, 3...) instead of the real database
        # question IDs -- common when an LLM renumbers questions for the
        # student instead of echoing the real id. If NONE of the provided
        # question_ids match but the counts line up, assume positional
        # order instead of silently failing every answer to None.
        questions_sorted = sorted(questions, key=lambda q: q.id)
        for q, a in zip(questions_sorted, answers):
            q.student_answer = a["student_answer"]
    else:
        for q in questions:
            if q.id in answer_map:
                q.student_answer = answer_map[q.id]

    db.flush()

    if session.test_type == "mcq":
        results = [
            {"question": q.question, "topic": q.topic, "correct_option": q.correct_option, "student_answer": q.student_answer}
            for q in questions
        ]
        report_data = Grader().grade(results)
        markdown_report = ReportGenerator(client).generate_markdown_report(report_data, grade=session.grade, subject=session.subject)
    else:
        results = [
            {"question": q.question, "topic": q.topic, "model_answer": q.model_answer, "student_answer": q.student_answer}
            for q in questions
        ]
        markdown_report = ReasoningReportGenerator(client).generate_report(results, grade=session.grade, subject=session.subject)

    session.completed = True
    db.commit()

    import markdown as md
    html_report = md.markdown(markdown_report, extensions=["tables"])

    return session, markdown_report, html_report