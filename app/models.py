"""
models.py

SQLAlchemy ORM models -- these define the DATABASE shape, not the API
contract. Never return these objects directly from an API endpoint;
always convert to a Pydantic schema first (see schemas.py) so fields
like hashed_password never leak into a response.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    subscription_active = Column(Boolean, default=False)
    subscription_expiry = Column(DateTime, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TestSession(Base):
    __tablename__ = "test_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    grade = Column(Integer, nullable=False)
    subject = Column(String, nullable=False)
    test_type = Column(String, nullable=False)  # "mcq" or "reasoning"

    completed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    questions = relationship("TestQuestion", back_populates="session", cascade="all, delete-orphan")


class TestQuestion(Base):
    __tablename__ = "test_questions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("test_sessions.id"), nullable=False)

    question = Column(Text, nullable=False)
    topic = Column(String, nullable=False)

    # MCQ-specific (nullable because reasoning questions don't use these)
    option_a = Column(String, nullable=True)
    option_b = Column(String, nullable=True)
    option_c = Column(String, nullable=True)
    option_d = Column(String, nullable=True)
    correct_option = Column(String, nullable=True)

    # Reasoning-specific
    model_answer = Column(Text, nullable=True)

    student_answer = Column(Text, nullable=True)

    session = relationship("TestSession", back_populates="questions")

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject = Column(String, nullable=False)

    # [{"role": "user"|"model", "text": str}, ...] -- only human-readable
    # turns, not the tool-calling negotiation (resolved per-request).
    messages = Column(JSON, nullable=False, default=list)

    # The currently in-progress test, if any. We track this ourselves
    # instead of relying on the model to remember the ID across turns --
    # its plain-text memory of a number mentioned earlier is unreliable.
    active_test_session_id = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PromptUsageLog(Base):
    __tablename__ = "prompt_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    name = Column(String, nullable=False)
    phone_number = Column(String, nullable=True)

    level = Column(String, nullable=False)    # "SSC (Matric)" | "HSSC (Intermediate)"
    group = Column(String, nullable=False)    # "Pre-Medical", "ICS (Computer Science)", etc.
    grade = Column(Integer, nullable=False)   # 9, 10, 11, 12

    subjects = Column(JSON, nullable=False)   # auto-derived, never client-supplied
    school_name = Column(String, nullable=True)

    user = relationship("User", backref="student_profile", uselist=False)