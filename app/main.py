"""
main.py

FastAPI entrypoint. Creates DB tables on startup (fine for SQLite/dev;
in real production you'd use Alembic migrations instead of
create_all -- flagged here, not implemented yet).
"""

from fastapi import FastAPI
from app.database import Base, engine
from app.routers import auth, test, profile, chat

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ilm-o-Maarifat API")

app.include_router(auth.router)
app.include_router(test.router)
app.include_router(profile.router)
app.include_router(chat.router)


@app.get("/")
def root():
    return {"status": "ok"}
