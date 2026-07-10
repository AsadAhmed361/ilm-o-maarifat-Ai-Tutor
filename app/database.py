"""
database.py

SQLAlchemy engine + session setup. SQLite for now -- switching to
Postgres later only requires changing DATABASE_URL, no code changes
elsewhere (that's the point of using an ORM instead of raw SQL).
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./ilm_o_maarifat.db")

# check_same_thread=False is SQLite-specific -- needed because FastAPI
# can access the DB from different threads. Not needed for Postgres.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency -- yields a DB session per request, closes it
    after the request finishes (even if an exception occurs).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
