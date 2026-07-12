# Ilm-o-Maarifat API

AI-powered educational platform backend for Sindh Board (Pakistan) students — SSC (Matric) and HSSC (Intermediate) levels. Generates AI-driven MCQ and reasoning-based tests, grades them, emails progress reports, and provides a conversational AI tutor with real function-calling agency.

## Project Background

This project started as a CLI prototype to learn AI engineering fundamentals (structured outputs, Gemini API, prompt design), then evolved into a production-oriented FastAPI backend once the core AI logic was validated. The CLI prototype lives in a separate repo and served as the architectural foundation for the business logic reused here (`app/services/`).

## Features

- **Auth**: JWT-based signup/login with bcrypt password hashing
- **Subscription gating**: test access requires an active subscription (`402 Payment Required` when inactive)
- **Student profiles**: level (SSC/HSSC), group (Pre-Medical, Pre-Engineering, ICS, etc.), subjects derived server-side from level+group — never trusted from client input
- **AI test generation**: MCQ and open-ended reasoning questions via Gemini structured output
- **Grading**: deterministic for MCQ, LLM-as-judge for reasoning
- **AI-generated progress reports**: markdown → HTML, emailed in the background after test submission
- **AI Tutor Chat**: subject-restricted conversational tutor using real Gemini function calling. The model decides when to call `start_test` / `submit_test` tools based on natural conversation — not a fixed pipeline. Supports Roman Urdu (with English technical terminology preserved), flags out-of-syllabus content, and rate-limits non-subscribers (10 messages/24hr; tests remain subscriber-only)

## Architecture

```
app/
├── main.py                    # FastAPI entrypoint
├── database.py                 # SQLAlchemy engine/session
├── models.py                    # DB models: User, StudentProfile, TestSession,
│                                   TestQuestion, ChatSession, PromptUsageLog
├── schemas.py                    # Pydantic request/response contracts
├── auth.py                        # JWT + password hashing + auth dependencies
├── gemini_client.py                # Singleton Gemini client (lru_cache) + MODEL_NAME
├── services/                        # AI + business logic (reused from CLI prototype)
│   ├── gemini_utils.py                 # Retry + exponential backoff wrapper
│   ├── question_generator.py            # MCQ generation (structured output)
│   ├── reasoning_question_generator.py
│   ├── grader.py                          # Deterministic MCQ grading
│   ├── report_generator.py                 # AI markdown report (MCQ)
│   ├── reasoning_report_generator.py         # Combined judge+report (reasoning)
│   ├── test_service.py                        # Shared create/submit-test logic --
│   │                                             used by BOTH REST endpoints and
│   │                                             the AI tutor's function-calling tools
│   ├── education_structure.py                  # Level+group -> subjects mapping
│   └── email_sender.py                          # HTML email via Gmail SMTP
└── routers/
├── auth.py     # /auth/signup, /auth/login, /auth/me
├── profile.py   # /profile, /profile/me (create/update, PATCH supported)
├── test.py       # /test/start, /test/{id}/submit
└── chat.py        # /chat/start, /chat/{id}/message -- AI tutor with tool calling
```

## Key Design Decisions

- **Server-side subject derivation**: subjects are computed from `level` + `group` via a fixed mapping (`services/education_structure.py`), never accepted from the client — prevents invalid combinations like "Pre-Medical + Computer Science".
- **Grading split by test type**: MCQ grading is pure deterministic code (no LLM, no hallucination risk); reasoning grading requires LLM judgment, so it's combined with report generation in a single call.
- **IDOR protection**: `/test/{session_id}/submit` and `/chat/{session_id}/message` both verify the session belongs to the requesting user before any read/write.
- **Transactional test creation**: test creation uses `db.flush()` instead of an early `db.commit()`, so a failed Gemini call never leaves an orphaned `TestSession` row in the database.
- **Background email**: report emailing is wrapped in try/except (including client construction, not just the send call) and dispatched via `BackgroundTasks`, so email failures never block or break the API response.
- **Shared service layer for chat tools**: `services/test_service.py` holds all test-creation/grading logic, called identically by REST `/test` endpoints and by the AI tutor's `start_test`/`submit_test` tools — zero duplicated business logic between the two interfaces.
- **Server-tracked conversation state**: the AI tutor's own memory of a `test_session_id` across turns is unreliable (models can renumber or forget IDs mid-conversation). `ChatSession.active_test_session_id` is tracked server-side and treated as the source of truth; the model-supplied ID is advisory only.
- **Defensive positional answer-matching**: if the model renumbers test questions for readability (e.g. always showing "1-10" instead of real DB IDs) and none of the submitted question_ids match, `test_service.py` falls back to positional matching rather than silently scoring every answer as blank.
- **Tool-level enforcement over prompt instructions**: business rules that must always hold (e.g. "don't start a second test while one is in progress", "tests require an active subscription") are enforced inside the tool functions themselves, not left to the system prompt alone — LLMs don't reliably follow static instructions under all conditions.

## Setup

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/docs` for interactive API docs.

## Dev Utilities

```bash
python -m scripts.activate_subscription user@example.com --days 30
```

Manually activates a subscription for testing (payment gateway integration is not yet implemented — see Roadmap).

## Roadmap

- [ ] Real payment gateway integration (Stripe or local equivalent) to replace manual subscription activation
- [ ] Alembic migrations (currently using `create_all`, fine for dev only)
- [ ] More reliable state-passing to the AI tutor without relying purely on prompt-following (currently mitigated with turn-specific dynamic reminders)
- [ ] AI evaluation: no current measurement of generated-question quality or grading consistency across runs
