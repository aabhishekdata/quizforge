import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..security import current_user

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED = {"pdf", "docx", "pptx", "md", "epub"}


def _queue() -> Queue:
    return Queue("generation", connection=Redis.from_url(settings.redis_url))


@router.post("", response_model=schemas.DocumentOut)
async def upload(
    file: UploadFile = File(...),
    high_quality: bool = Form(False),
    subject_id: int | None = Form(None),
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type .{ext} - use PDF, DOCX, PPTX, EPUB, or MD")

    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(400, f"File is over the {settings.max_upload_mb}MB limit")
    if subject_id is not None:
        subject = db.get(models.Subject, subject_id)
        if not subject or subject.owner_id != user.id:
            raise HTTPException(404, "Subject not found")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored = upload_dir / f"{uuid.uuid4().hex}.{ext}"
    stored.write_bytes(data)

    doc = models.Document(
        owner_id=user.id, filename=file.filename, filetype=ext, stored_path=str(stored))
    db.add(doc)
    db.commit()
    db.refresh(doc)

    _queue().enqueue(
        "app.services.tasks.generate_deck_from_document",
        doc.id, high_quality, subject_id, job_timeout=1800)
    return doc


@router.get("", response_model=list[schemas.DocumentOut])
def list_documents(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(models.Document)
        .where(models.Document.owner_id == user.id)
        .order_by(models.Document.created_at.desc())
    ).all()


@router.get("/{doc_id}", response_model=schemas.DocumentOut)
def get_document(doc_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    doc = db.get(models.Document, doc_id)
    if not doc or doc.owner_id != user.id:
        raise HTTPException(404, "Document not found")
    return doc
