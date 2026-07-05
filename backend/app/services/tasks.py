"""RQ background job: document -> concept map -> generated deck."""
from .. import models
from ..config import settings
from ..database import SessionLocal
from . import generation, parsing, xp


def _set(db, doc: models.Document, status=None, progress=None, error=None):
    if status:
        doc.status = status
    if progress:
        doc.progress = progress
    if error is not None:
        doc.error = error
    db.commit()


def _delete_partial_deck(db, deck: models.Deck | None):
    if deck is None:
        return
    db.delete(deck)
    db.commit()


def generate_deck_from_document(document_id: int, high_quality: bool = False):
    db = SessionLocal()
    doc = db.get(models.Document, document_id)
    if not doc:
        db.close()
        return

    deck = None
    try:
        _set(db, doc, status=models.DocStatus.parsing, progress="Reading document...")
        sections = parsing.extract_text(doc.stored_path, doc.filetype, settings.max_pages)
        chunks = parsing.chunk_sections(sections)

        _set(
            db,
            doc,
            status=models.DocStatus.generating,
            progress=f"Parsed {len(sections)} sections - building concept map...",
        )
        title = doc.filename.rsplit(".", 1)[0][:200]
        skeleton = generation.build_subject_skeleton(
            title,
            doc.filetype.upper(),
            sections,
            high_quality=high_quality,
        )
        subject = skeleton.get("subject") or title

        deck = models.Deck(
            owner_id=doc.owner_id,
            document_id=doc.id,
            title=title,
            description=f"Generated from {doc.filename}. Subject map: {subject}",
        )
        db.add(deck)
        db.flush()

        total = 0
        previous_fronts: list[str] = []
        for i, (label, text) in enumerate(chunks, start=1):
            cards = generation.generate_cards_for_chunk(
                text,
                label,
                settings.cards_per_chunk,
                high_quality=high_quality,
                skeleton=skeleton,
                previous_fronts=previous_fronts,
                chunk_index=i,
                total_chunks=len(chunks),
            )
            for c in cards:
                db.add(models.Card(deck_id=deck.id, **c))
                previous_fronts.append(c["front"])
            total += len(cards)
            _set(db, doc, progress=f"Chunk {i}/{len(chunks)} - {total} cards so far...")

        if total == 0:
            raise parsing.ParseError("The model returned no usable cards for this document")

        xp.award(db, doc.owner_id, 15, "document_upload", {"document_id": doc.id})
        deck_count = db.query(models.Deck).filter_by(owner_id=doc.owner_id).count()
        if deck_count >= 1:
            xp.grant(db, doc.owner_id, "first_deck")
        doc_count = db.query(models.Document).filter_by(owner_id=doc.owner_id).count()
        if doc_count >= 5:
            xp.grant(db, doc.owner_id, "uploader")

        _set(db, doc, status=models.DocStatus.ready, progress=f"Done - {total} cards ready to review")
    except parsing.ParseError as e:
        _delete_partial_deck(db, deck)
        _set(db, doc, status=models.DocStatus.failed, progress="Failed", error=str(e))
    except Exception as e:  # noqa: BLE001
        _delete_partial_deck(db, deck)
        _set(
            db,
            doc,
            status=models.DocStatus.failed,
            progress="Failed",
            error=f"Unexpected error: {type(e).__name__}: {e}",
        )
    finally:
        db.close()
