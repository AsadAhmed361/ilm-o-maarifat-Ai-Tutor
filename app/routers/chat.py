"""
routers/chat.py

AI tutor chat with function calling. The model decides when to call
start_test / submit_test based on natural conversation -- this is real
agentic behavior, not a fixed pipeline.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from google import genai
from google.genai import types

from app.database import get_db
from app import models, schemas, auth
from app.gemini_client import get_gemini_client, MODEL_NAME
from app.services.test_service import create_test_session, submit_test_session
from app.services.email_sender import EmailSender

router = APIRouter(prefix="/chat", tags=["chat"])

FREE_TIER_DAILY_LIMIT = 10


def _check_rate_limit(db: Session, user: models.User):
    if user.subscription_active:
        return  # subscribers -- unlimited

    cutoff = datetime.utcnow() - timedelta(hours=24)
    count = db.query(models.PromptUsageLog).filter(
        models.PromptUsageLog.user_id == user.id,
        models.PromptUsageLog.created_at >= cutoff,
    ).count()

    if count >= FREE_TIER_DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Free tier limit reached ({FREE_TIER_DAILY_LIMIT} messages per 24 hours). Subscribe for unlimited access.",
        )


def _build_system_prompt(profile: models.StudentProfile, subject: str) -> str:
    return f"""
You are a friendly, patient AI tutor helping a grade {profile.grade} {subject}
student following the {profile.level} Sindh Board of Secondary Education
(Pakistan) syllabus, {profile.group} group.

Rules you MUST follow:
1. Only discuss {subject}. If the student asks about a different subject,
   gently tell them to start a separate chat for that subject.
2. Teach like a supportive teacher: explain clearly, check understanding,
   correct misunderstandings kindly.
3. If a question goes beyond the standard {profile.level} {subject}
   syllabus, you may still explain it, but you MUST clearly say it is
   "outside your current course syllabus" so the student knows it won't
   be tested.
4. If the student asks to take a test/quiz, call the start_test tool
   with the appropriate test_type ("mcq" or "reasoning").
5. Once the student has given you answers to all questions from a test
   started in this conversation, call the submit_test tool -- NEVER
   invent, estimate, or reveal a score or correct answers yourself under
   any circumstances. Only the submit_test tool's result is authoritative.
6. If a test is already in progress (you already called start_test and
   are waiting for answers), do NOT call start_test again -- wait for
   the student's answers and call submit_test instead.
7. When the student asks for a test, ALWAYS call the start_test tool
   immediately -- do not ask the student whether they are subscribed,
   and do not guess their subscription status yourself. The tool will
   tell you if a subscription is required. If the tool returns an
   error about needing a subscription, relay that clearly and kindly
   to the student.
8. Language: If the student writes in Roman Urdu (Urdu written in
   English/Latin script), reply in Roman Urdu too. ALWAYS keep subject
   and curriculum terminology -- scientific terms, formulas, subject
   names, technical vocabulary -- in English, since the official Sindh
   Board curriculum and exams use English terms. Blend natural Roman
   Urdu sentences with English technical terms.
9. If a tool returns an error (e.g. AI service temporarily unavailable,
   quota exceeded), apologize briefly and ask the student to try again
   in a little while -- do not expose raw technical error details.
"""


def _build_tools() -> types.Tool:
    start_test_decl = types.FunctionDeclaration(
        name="start_test",
        description="Starts a new test in the current subject and returns the questions.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "test_type": types.Schema(type=types.Type.STRING, enum=["mcq", "reasoning"]),
            },
            required=["test_type"],
        ),
    )

    submit_test_decl = types.FunctionDeclaration(
        name="submit_test",
        description="Submits the student's answers for a started test and returns the real grading report.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "test_session_id": types.Schema(type=types.Type.INTEGER),
                "answers": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "question_id": types.Schema(type=types.Type.INTEGER),
                            "student_answer": types.Schema(type=types.Type.STRING),
                        },
                        required=["question_id", "student_answer"],
                    ),
                ),
            },
            required=["test_session_id", "answers"],
        ),
    )

    return types.Tool(function_declarations=[start_test_decl, submit_test_decl])


@router.post("/start", response_model=schemas.ChatStartResponse)
def start_chat(
    request: schemas.ChatStartRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(models.StudentProfile).filter(models.StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Create your student profile before starting a chat")

    if request.subject not in profile.subjects:
        raise HTTPException(status_code=400, detail=f"{request.subject} is not one of your enrolled subjects: {profile.subjects}")

    greeting = f"Hi {profile.name}! I'm your {request.subject} tutor. What would you like to work on today?"

    session = models.ChatSession(
        user_id=current_user.id,
        subject=request.subject,
        messages=[{"role": "model", "text": greeting}],
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return schemas.ChatStartResponse(chat_session_id=session.id, reply=greeting)


@router.post("/{session_id}/message", response_model=schemas.ChatMessageResponse)
def send_message(
    session_id: int,
    request: schemas.ChatMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
    client: genai.Client = Depends(get_gemini_client),
):
    chat_session = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.id == session_id, models.ChatSession.user_id == current_user.id)
        .first()
    )
    if not chat_session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    _check_rate_limit(db, current_user)
    profile = db.query(models.StudentProfile).filter(models.StudentProfile.user_id == current_user.id).first()

    # --- Tools, closed over this request's db/user/client/background_tasks ---
    def start_test(test_type: str) -> dict:
        if not current_user.subscription_active:
            return {"error": "Tests are a subscriber-only feature. The student needs an active subscription to take MCQ or reasoning tests."}
        if chat_session.active_test_session_id is not None:
            return {
                "error": "A test is already in progress for this student. Do NOT start a new test. "
                         "Call submit_test with the student's answers instead."
            }
        try:
            test_session, safe_questions = create_test_session(
                db, current_user, profile.grade, chat_session.subject, test_type, client
            )
            chat_session.active_test_session_id = test_session.id
            db.commit()
            return {"test_session_id": test_session.id, "questions": safe_questions}
        except (ValueError, RuntimeError) as e:
            return {"error": f"Could not start the test right now: {e}"}

    def submit_test(test_session_id: int, answers: list[dict]) -> dict:
        real_session_id = chat_session.active_test_session_id
        if real_session_id is None:
            return {"error": "No test is currently in progress for this student."}

        try:
            session, markdown_report, html_report = submit_test_session(db, current_user, real_session_id, answers, client)
            chat_session.active_test_session_id = None
            db.commit()
            try:
                mailer = EmailSender()
                background_tasks.add_task(
                    mailer.send, html_report, markdown_report, current_user.email,
                    subject=f"Grade {session.grade} {session.subject} Progress Report",
                )
            except Exception as e:
                print(f"Email sending skipped due to error: {e}")
            return {"report": markdown_report}
        except (LookupError, ValueError, RuntimeError) as e:
            return {"error": f"Could not grade the test right now: {e}"}

    tool_functions = {"start_test": start_test, "submit_test": submit_test}

    contents = [
        types.Content(role=m["role"], parts=[types.Part.from_text(text=m["text"])])
        for m in chat_session.messages
        if m.get("text")  # defensively skip any corrupted/empty historical entries
    ]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=request.message)]))

    # If a test is already in progress, inject a strong, state-specific
    # reminder for THIS turn only (not persisted). Generic static rules
    # in the system prompt have proven unreliable -- the model sometimes
    # ignores them and fabricates an excuse instead of calling the tool.
    # A reminder naming the exact active session ID is much harder to ignore.
    if chat_session.active_test_session_id is not None:
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=(
                    f"[SYSTEM REMINDER: There is an active test in progress, "
                    f"test_session_id={chat_session.active_test_session_id}. "
                    f"If my previous message contains answers to the test questions, "
                    f"you MUST call the submit_test tool now with test_session_id="
                    f"{chat_session.active_test_session_id} and my answers. "
                    f"Do NOT respond with an excuse or apology instead of calling the tool.]"
                ))],
            )
        )

    config = types.GenerateContentConfig(
        system_instruction=_build_system_prompt(profile, chat_session.subject),
        tools=[_build_tools()],
    )

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=contents, config=config)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI tutor temporarily unavailable: {e}")

    # Loop instead of a single if-check: the model can chain multiple
    # tool calls in one turn. Cap at 3 so this can never infinite-loop.
    MAX_TOOL_CALLS = 3
    for _ in range(MAX_TOOL_CALLS):
        function_call = None
        for part in response.candidates[0].content.parts:
            if part.function_call:
                function_call = part.function_call
                break

        print(f"DEBUG: function_call this round = {function_call}")

        if not function_call:
            break  # model gave plain text -- we're done    

        result = tool_functions[function_call.name](**function_call.args)

        # Don't echo back the model's raw response content -- thinking
        # models (gemini-3-flash-preview) include internal "thought"
        # parts whose exact shape isn't safe to replay verbatim.
        # Reconstruct a minimal, guaranteed-clean turn containing ONLY
        # the function_call itself.
        contents.append(response.candidates[0].content)

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_function_response(name=function_call.name, response=result)],
            )
        )
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=contents, config=config)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"AI tutor temporarily unavailable: {e}")

    final_text = response.text or "Sorry, something went wrong generating a response. Please try again."

    chat_session.messages = chat_session.messages + [
        {"role": "user", "text": request.message},
        {"role": "model", "text": final_text},
    ]

    if not current_user.subscription_active:
        db.add(models.PromptUsageLog(user_id=current_user.id))

    db.commit()

    return schemas.ChatMessageResponse(reply=final_text)