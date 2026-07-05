from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import current_user, admin_user
from ..services import xp
from ..services import deck_io

router = APIRouter(prefix="/api/decks", tags=["decks"])


def _download_filename(title: str, ext: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-")
    safe = "-".join(part for part in safe.split("-") if part) or "deck"
    return f"{safe[:80]}.{ext}"


def _accessible_deck(db: Session, deck_id: int, user: models.User) -> models.Deck:
    deck = db.get(models.Deck, deck_id)
    if not deck:
        raise HTTPException(404, "Deck not found")
    if deck.owner_id == user.id:
        return deck
    shared = db.scalar(select(models.DeckShare).where(
        models.DeckShare.deck_id == deck_id, models.DeckShare.user_id == user.id))
    if shared:
        return deck
    group_shared = db.scalar(
        select(models.DeckGroupShare)
        .join(models.StudyGroupMember, models.StudyGroupMember.group_id == models.DeckGroupShare.group_id)
        .where(
            models.DeckGroupShare.deck_id == deck_id,
            models.StudyGroupMember.user_id == user.id,
        )
    )
    if not group_shared:
        raise HTTPException(404, "Deck not found")
    return deck


def _deck_out(db: Session, deck: models.Deck, user: models.User) -> schemas.DeckOut:
    card_count = db.scalar(select(func.count(models.Card.id)).where(models.Card.deck_id == deck.id)) or 0
    due_count = 0
    if deck.smart_review:
        due_count = db.scalar(
            select(func.count(models.CardReview.id))
            .join(models.Card, models.Card.id == models.CardReview.card_id)
            .where(models.Card.deck_id == deck.id,
                   models.CardReview.user_id == user.id,
                   models.CardReview.due <= datetime.utcnow())) or 0
    owner = db.get(models.User, deck.owner_id)
    return schemas.DeckOut(
        id=deck.id, title=deck.title, description=deck.description,
        owner_id=deck.owner_id, owner_username=owner.username if owner else "",
        is_shared_with_me=deck.owner_id != user.id,
        smart_review=deck.smart_review, card_count=card_count,
        due_count=due_count, created_at=deck.created_at)


@router.get("", response_model=list[schemas.DeckOut])
def list_decks(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    shared_ids = select(models.DeckShare.deck_id).where(models.DeckShare.user_id == user.id)
    group_shared_ids = (
        select(models.DeckGroupShare.deck_id)
        .join(models.StudyGroupMember, models.StudyGroupMember.group_id == models.DeckGroupShare.group_id)
        .where(models.StudyGroupMember.user_id == user.id)
    )
    decks = db.scalars(
        select(models.Deck)
        .where(or_(
            models.Deck.owner_id == user.id,
            models.Deck.id.in_(shared_ids),
            models.Deck.id.in_(group_shared_ids),
        ))
        .order_by(models.Deck.created_at.desc())
    ).all()
    return [_deck_out(db, d, user) for d in decks]


@router.post("", response_model=schemas.DeckOut)
def create_deck(body: schemas.DeckCreate, user: models.User = Depends(current_user),
                db: Session = Depends(get_db)):
    deck = models.Deck(owner_id=user.id, title=body.title, description=body.description)
    db.add(deck)
    db.commit()
    xp.grant(db, user.id, "first_deck")
    db.commit()
    return _deck_out(db, deck, user)


@router.post("/import", response_model=schemas.DeckOut)
async def import_deck(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    data = await file.read()
    imported = deck_io.parse_import(file.filename or "", data, title=title)
    deck = models.Deck(owner_id=user.id, title=imported.title, description=imported.description)
    db.add(deck)
    db.flush()
    for card in imported.cards:
        db.add(models.Card(deck_id=deck.id, **card))
    db.commit()
    db.refresh(deck)
    xp.grant(db, user.id, "first_deck")
    db.commit()
    return _deck_out(db, deck, user)


@router.get("/{deck_id}", response_model=schemas.DeckOut)
def get_deck(deck_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    return _deck_out(db, _accessible_deck(db, deck_id, user), user)


@router.get("/{deck_id}/export.json")
def export_deck_json(deck_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    deck = _accessible_deck(db, deck_id, user)
    cards = db.scalars(select(models.Card).where(models.Card.deck_id == deck.id)).all()
    return Response(
        content=deck_io.deck_to_json(deck, cards),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{_download_filename(deck.title, "json")}"'},
    )


@router.get("/{deck_id}/export.csv")
def export_deck_csv(deck_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    deck = _accessible_deck(db, deck_id, user)
    cards = db.scalars(select(models.Card).where(models.Card.deck_id == deck.id)).all()
    return Response(
        content=deck_io.deck_to_csv(cards),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_download_filename(deck.title, "csv")}"'},
    )


@router.patch("/{deck_id}", response_model=schemas.DeckOut)
def update_deck(deck_id: int, body: schemas.DeckUpdate,
                user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    deck = _accessible_deck(db, deck_id, user)
    if deck.owner_id != user.id:
        raise HTTPException(403, "Only the owner can edit this deck")
    if body.title is not None:
        deck.title = body.title
    if body.description is not None:
        deck.description = body.description
    if body.smart_review is not None:
        deck.smart_review = body.smart_review
        if body.smart_review:
            xp.grant(db, user.id, "smart_start")
    db.commit()
    return _deck_out(db, deck, user)


@router.delete("/{deck_id}")
def delete_deck(deck_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    deck = _accessible_deck(db, deck_id, user)
    if deck.owner_id != user.id:
        raise HTTPException(403, "Only the owner can delete this deck")
    db.query(models.DeckShare).filter_by(deck_id=deck.id).delete()
    db.query(models.DeckGroupShare).filter_by(deck_id=deck.id).delete()
    db.delete(deck)
    db.commit()
    return {"ok": True}


@router.post("/{deck_id}/share")
def share_deck(deck_id: int, body: schemas.ShareIn,
               admin: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    deck = db.get(models.Deck, deck_id)
    if not deck:
        raise HTTPException(404, "Deck not found")
    target = db.scalar(select(models.User).where(models.User.username == body.username))
    if not target:
        raise HTTPException(404, f"No user named {body.username}")
    if target.id == admin.id:
        raise HTTPException(400, "That's you")
    exists = db.scalar(select(models.DeckShare).where(
        models.DeckShare.deck_id == deck.id, models.DeckShare.user_id == target.id))
    if not exists:
        db.add(models.DeckShare(deck_id=deck.id, user_id=target.id))
        deck.is_shared = True
        xp.grant(db, admin.id, "sharer")
        db.commit()
    return {"ok": True, "shared_with": body.username}


@router.post("/{deck_id}/share-group")
def share_deck_with_group(deck_id: int, body: schemas.GroupShareIn,
                          admin: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    deck = db.get(models.Deck, deck_id)
    if not deck:
        raise HTTPException(404, "Deck not found")
    group = db.get(models.StudyGroup, body.group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    exists = db.scalar(select(models.DeckGroupShare).where(
        models.DeckGroupShare.deck_id == deck.id,
        models.DeckGroupShare.group_id == group.id,
    ))
    if not exists:
        db.add(models.DeckGroupShare(deck_id=deck.id, group_id=group.id, shared_by=admin.id))
        deck.is_shared = True
        xp.grant(db, admin.id, "sharer")
        db.commit()
    return {"ok": True, "shared_with_group": group.name}


@router.get("/{deck_id}/cards", response_model=list[schemas.CardOut])
def list_cards(deck_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    deck = _accessible_deck(db, deck_id, user)
    return db.scalars(select(models.Card).where(models.Card.deck_id == deck.id)).all()


@router.post("/{deck_id}/cards", response_model=schemas.CardOut)
def create_card(deck_id: int, body: schemas.CardCreate,
                user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    deck = _accessible_deck(db, deck_id, user)
    if deck.owner_id != user.id:
        raise HTTPException(403, "Only the owner can add cards")
    card = models.Card(deck_id=deck.id, front=body.front, back=body.back,
                       difficulty=body.difficulty if body.difficulty in ("easy", "medium", "hard") else "medium")
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.patch("/{deck_id}/cards/{card_id}", response_model=schemas.CardOut)
def update_card(deck_id: int, card_id: int, body: schemas.CardUpdate,
                user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    deck = _accessible_deck(db, deck_id, user)
    if deck.owner_id != user.id:
        raise HTTPException(403, "Only the owner can edit cards")
    card = db.get(models.Card, card_id)
    if not card or card.deck_id != deck.id:
        raise HTTPException(404, "Card not found")
    if body.front is not None:
        card.front = body.front
    if body.back is not None:
        card.back = body.back
    if body.difficulty in ("easy", "medium", "hard"):
        card.difficulty = body.difficulty
    db.commit()
    return card


@router.delete("/{deck_id}/cards/{card_id}")
def delete_card(deck_id: int, card_id: int,
                user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    deck = _accessible_deck(db, deck_id, user)
    if deck.owner_id != user.id:
        raise HTTPException(403, "Only the owner can delete cards")
    card = db.get(models.Card, card_id)
    if not card or card.deck_id != deck.id:
        raise HTTPException(404, "Card not found")
    db.delete(card)
    db.commit()
    return {"ok": True}
