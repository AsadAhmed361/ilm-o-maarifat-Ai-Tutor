"""
schemas.py

Pydantic schemas -- the API's public contract. Deliberately separate
from models.py (the DB shape). UserOut never includes hashed_password.
"""

from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, Literal


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    subscription_active: bool
    subscription_expiry: Optional[datetime] = None

    class Config:
        from_attributes = True  # allows creating this from a SQLAlchemy object


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None


class TestStartRequest(BaseModel):
    grade: int
    subject: str
    test_type: Literal["mcq", "reasoning"]


class QuestionOut(BaseModel):
    """
    Deliberately excludes correct_option and model_answer -- the client
    (student) must never receive the answer key. Only fields safe to
    show before grading go here.
    """
    id: int
    question: str
    topic: str
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None

    class Config:
        from_attributes = True


class TestStartResponse(BaseModel):
    session_id: int
    test_type: str
    questions: list[QuestionOut]


class AnswerSubmit(BaseModel):
    question_id: int
    student_answer: str


class TestSubmitRequest(BaseModel):
    answers: list[AnswerSubmit]


class TestSubmitResponse(BaseModel):
    session_id: int
    html_report: str


class StudentProfileCreate(BaseModel):
    name: str
    phone_number: Optional[str] = None
    level: Literal["SSC (Matric)", "HSSC (Intermediate)"]
    group: Literal[
        "Science (Biology)",
        "Science (Computer Science)",
        "Pre-Medical",
        "Pre-Engineering",
        "ICS (Computer Science)",
    ]
    grade: int
    school_name: Optional[str] = None

class StudentProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    level: Optional[Literal["SSC (Matric)", "HSSC (Intermediate)"]] = None
    group: Optional[Literal[
        "Science (Biology)",
        "Science (Computer Science)",
        "Pre-Medical",
        "Pre-Engineering",
        "ICS (Computer Science)",
    ]] = None
    grade: Optional[int] = None
    school_name: Optional[str] = None

class StudentProfileOut(BaseModel):
    id: int
    name: str
    phone_number: Optional[str] = None
    level: str
    group: str
    grade: int
    subjects: list[str]
    school_name: Optional[str] = None

    class Config:
        from_attributes = True


class ChatStartRequest(BaseModel):
    subject: str


class ChatStartResponse(BaseModel):
    chat_session_id: int
    reply: str


class ChatMessageRequest(BaseModel):
    message: str


class ChatMessageResponse(BaseModel):
    reply: str