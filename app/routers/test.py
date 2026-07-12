"""
routers/test.py

Thin HTTP layer over services/test_service.py -- translates plain
Python exceptions into HTTPException, handles auth/subscription
dependencies. All actual test-creation/grading logic lives in the
service layer, shared with the AI tutor's tools (routers/chat.py).
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas, auth
from app.gemini_client import get_gemini_client
from app.services.test_service import create_test_session, submit_test_session
from app.services.email_sender import EmailSender

router = APIRouter(prefix="/test", tags=["test"])


@router.post("/start", response_model=schemas.TestStartResponse)
def start_test(
    request: schemas.TestStartRequest,
    current_user: models.User = Depends(auth.require_active_subscription),
    db: Session = Depends(get_db),
    client=Depends(get_gemini_client),
):
    try:
        session, safe_questions = create_test_session(
            db, current_user, request.grade, request.subject, request.test_type, client
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"AI service temporarily unavailable: {e}")

    return schemas.TestStartResponse(
        session_id=session.id,
        test_type=session.test_type,
        questions=safe_questions,
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
    answers = [a.model_dump() for a in request.answers]

    try:
        session, markdown_report, html_report = submit_test_session(db, current_user, session_id, answers, client)
    except LookupError:
        raise HTTPException(status_code=404, detail="Test session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"AI service temporarily unavailable: {e}")

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