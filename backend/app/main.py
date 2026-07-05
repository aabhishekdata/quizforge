from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, select, text

from .config import settings
from .database import Base, engine, SessionLocal
from . import models  # noqa: F401 (register models)
from .routers import auth, documents, decks, study, gamification
from .services.xp import seed_achievements
from .services import xp as xp_service

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server; prod is same-origin via Caddy
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(decks.router)
app.include_router(study.router)
app.include_router(gamification.router)
app.include_router(gamification.admin_router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    _ensure_lightweight_migrations()
    db = SessionLocal()
    try:
        seed_achievements(db)
        # bootstrap: if no users and no unused invites exist, create one and log it
        has_users = db.query(models.User).count() > 0
        unused = db.scalar(select(models.InviteCode).where(models.InviteCode.used_by.is_(None)))
        if not has_users and not unused:
            from .routers.gamification import _new_code
            code = models.InviteCode(code=_new_code())
            db.add(code)
            db.commit()
            print(f"\n=== FIRST-RUN INVITE CODE: {code.code} ===\n", flush=True)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"ok": True}


def _ensure_lightweight_migrations():
    """Small create_all companion for local/dev installs without Alembic yet."""
    inspector = inspect(engine)
    if "cards" not in inspector.get_table_names():
        return
    card_columns = {c["name"] for c in inspector.get_columns("cards")}
    with engine.begin() as conn:
        if "card_type" not in card_columns:
            conn.execute(text("ALTER TABLE cards ADD COLUMN card_type VARCHAR(20) DEFAULT 'recall' NOT NULL"))
        if "learning_meta" not in card_columns:
            conn.execute(text("ALTER TABLE cards ADD COLUMN learning_meta JSON"))
