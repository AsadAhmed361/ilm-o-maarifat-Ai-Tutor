# Ilm-o-Maarifat API

AI-powered educational platform backend for Sindh Board (Pakistan) students — SSC (Matric) and HSSC (Intermediate) levels. Generates AI-driven MCQ and reasoning-based tests, grades them, and emails progress reports.

## Project Background

This project started as a CLI prototype to learn AI engineering fundamentals (structured outputs, Gemini API, prompt design), then evolved into a production-oriented FastAPI backend once the core AI logic was validated. The CLI prototype lives in a separate repo and served as the architectural foundation for the business logic reused here (`app/services/`).

## Features

- **Auth**: JWT-based signup/login with bcrypt password hashing
- **Subscription gating**: test access requires an active subscription (`402 Payment Required` when inactive)
- **Student profiles**: level (SSC/HSSC), group (Pre-Medical, Pre-Engineering, ICS, etc.), subjects derived server-side from level+group — never trusted from client input
- **AI test generation**: MCQ and open-ended reasoning questions via Gemini structured output
- **Grading**: deterministic for MCQ, LLM-as-judge for reasoning
- **AI-generated progress reports**: markdown → HTML, emailed in the background after test submission

## Architecture

```
app/
├── main.py           # FastAPI entrypoint
├── database.py        # SQLAlchemy engine/session
├── models.py           # DB models: User, StudentProfile, TestSession, TestQuestion
├── schemas.py           # Pydantic request/response contracts
├── auth.py               # JWT + password hashing + auth dependencies
├── gemini_client.py       # Singleton Gemini client (cached via lru_cache)
├── services/                # AI + business logic (reused from CLI prototype)
│   ├── gemini_utils.py         # Retry + exponential backoff wrapper
│   ├── question_generator.py    # MCQ generation (structured output)
│   ├── reasoning_question_generator.py
│   ├── grader.py                  # Deterministic MCQ grading
│   ├── report_generator.py         # AI markdown report (MCQ)
│   ├── reasoning_report_generator.py  # Combined judge+report (reasoning)
│   └── email_sender.py                 # HTML email via Gmail SMTP
└── routers/
    ├── auth.py     # /auth/signup, /auth/login, /auth/me
    ├── profile.py   # /profile, /profile/me
    └── test.py       # /test/start, /test/{id}/submit
```

## Key Design Decisions

- **Server-side subject derivation**: subjects are computed from `level` + `group` via a fixed mapping (`services/education_structure.py`), never accepted from the client — prevents invalid combinations like "Pre-Medical + Computer Science".
- **Grading split by test type**: MCQ grading is pure deterministic code (no LLM, no hallucination risk); reasoning grading requires LLM judgment, so it's combined with report generation in a single call.
- **IDOR protection**: `/test/{session_id}/submit` verifies the session belongs to the requesting user before any read/write.
- **Transactional test creation**: `/test/start` uses `db.flush()` instead of an early `db.commit()`, so a failed Gemini call never leaves an orphaned `TestSession` row in the database.
- **Background email**: report emailing is wrapped in try/except and dispatched via `BackgroundTasks`, so email failures (missing config, SMTP errors) never block or break the API response.

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
- [ ] Study assistant with Gemini function calling (natural-language test start, score lookup, etc.)
- [ ] Alembic migrations (currently using `create_all`, fine for dev only)
