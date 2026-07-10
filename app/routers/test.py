"""
routers/test.py

/test/start -- protected by require_active_subscription. Generates
questions (MCQ or reasoning), persists them to the DB tied to a new
TestSession, and returns them to the client WITHOUT correct answers.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import markdown

from app.database import get_db
from app import models, schemas, auth
from app.gemini_client import get_gemini_client
from app.services.question_generator import QuestionGenerator
from app.services.reasoning_question_generator import ReasoningQuestionGenerator
from app.services.grader import Grader
from app.services.report_generator import ReportGenerator
from app.services.reasoning_report_generator import ReasoningReportGenerator
from app.services.email_sender import EmailSender

router = APIRouter(prefix="/test", tags=["test"])


@router.post("/start", response_model=schemas.TestStartResponse)
def start_test(
    request: schemas.TestStartRequest,
    current_user: models.User = Depends(auth.require_active_subscription),
    db: Session = Depends(get_db),
    client=Depends(get_gemini_client),
):
    session = models.TestSession(
        user_id=current_user.id,
        grade=request.grade,
        subject=request.subject,
        test_type=request.test_type,
    )
    db.add(session)
    db.flush()  # assigns session.id WITHOUT committing to DB yet

    if request.test_type == "mcq":
        generator = QuestionGenerator(client)
        raw_questions = generator.generate(num_questions=10, grade=request.grade, subject=request.subject)
    else:  # reasoning
        generator = ReasoningQuestionGenerator(client)
        raw_questions = generator.generate(num_questions=5, grade=request.grade, subject=request.subject)

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

    # ONE commit at the very end -- if generate() raised an exception above,
    # we never reach this line, and the session.add() from earlier is
    # rolled back automatically (nothing was ever committed to disk).
    db.commit()
    db.refresh(session)
    for q in db_questions:
        db.refresh(q)

    return schemas.TestStartResponse(
        session_id=session.id,
        test_type=session.test_type,
        questions=db_questions,
    )


@router.post("/{session_id}/submit", response_model=schemas.TestSubmitResponse)
def submit_test(
    session_id: int,
    request: schemas.TestSubmitRequest,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
    client=Depends(get_gemini_client),
):
    # IDOR check: session must exist AND belong to the requesting user.
    # Using 404 (not 403) for both "doesn't exist" and "not yours" --
    # this avoids leaking which session IDs exist to other users.
    session = (
        db.query(models.TestSession)
        .filter(models.TestSession.id == session_id, models.TestSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Test session not found")

    if session.completed:
        raise HTTPException(status_code=400, detail="This test has already been submitted")

    # Map incoming answers by question_id for O(1) lookup
    answer_map = {a.question_id: a.student_answer for a in request.answers}

    questions = db.query(models.TestQuestion).filter(models.TestQuestion.session_id == session_id).all()
    for q in questions:
        if q.id in answer_map:
            q.student_answer = answer_map[q.id]

    db.flush()

    if session.test_type == "mcq":
        results = [
            {
                "question": q.question,
                "topic": q.topic,
                "correct_option": q.correct_option,
                "student_answer": q.student_answer,
            }
            for q in questions
        ]
        grader = Grader()
        report_data = grader.grade(results)

        reporter = ReportGenerator(client)
        markdown_report = reporter.generate_markdown_report(report_data, grade=session.grade, subject=session.subject)

    else:  # reasoning
        results = [
            {
                "question": q.question,
                "topic": q.topic,
                "model_answer": q.model_answer,
                "student_answer": q.student_answer,
            }
            for q in questions
        ]
        reporter = ReasoningReportGenerator(client)
        markdown_report = reporter.generate_report(results, grade=session.grade, subject=session.subject)

    session.completed = True
    db.commit()

    # Single conversion point -- reused for both the API response and
    # the email body, so markdown->HTML logic isn't duplicated.
    html_report = markdown.markdown(markdown_report, extensions=["tables"])

    # Email sending is wrapped defensively -- ANY failure here (missing
    # SMTP config, EmailSender construction failing, etc.) must NEVER
    # prevent the client from getting their report. This is intentionally
    # OUTSIDE background_tasks because EmailSender() itself can raise
    # synchronously (e.g. missing env vars) before the task even queues.
    try:
        mailer = EmailSender()
        background_tasks.add_task(
            mailer.send,
            html_report,
            markdown_report,
            current_user.email,
            subject=f"Grade {session.grade} {session.subject} Progress Report",
        )
    except Exception as e:
        print(f"Email sending skipped due to error: {e}")

    return schemas.TestSubmitResponse(session_id=session.id, html_report=html_report)
