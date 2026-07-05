import random
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import current_user
from ..services import xp, fsrs
from .decks import _accessible_deck

router = APIRouter(prefix="/api/study", tags=["study"])


@router.get("/{deck_id}/session", response_model=list[schemas.CardOut])
def get_session_cards(
    deck_id: int,
    mode: str = Query("flashcard"),
    limit: int = Query(20, le=100),
    smart: bool = Query(False),
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    deck = _accessible_deck(db, deck_id, user)
    cards = db.scalars(select(models.Card).where(models.Card.deck_id == deck.id)).all()
    if mode == "mcq":
        cards = [c for c in cards if c.mcq_options]
    if not cards:
        raise HTTPException(400, "No cards available for this mode — try flashcards instead")

    if smart and deck.smart_review:
        reviews = {r.card_id: r for r in db.scalars(
            select(models.CardReview).where(
                models.CardReview.user_id == user.id,
                models.CardReview.card_id.in_([c.id for c in cards]))).all()}
        now = datetime.utcnow()
        due = [c for c in cards if c.id not in reviews or reviews[c.id].due <= now]
        # due first, newest-learned last
        cards = due if due else []
        if not cards:
            raise HTTPException(400, "Nothing due right now — come back later or use free practice")

    random.shuffle(cards)
    return cards[:limit]


@router.post("/review", response_model=schemas.ReviewOut)
def submit_review(body: schemas.ReviewIn, user: models.User = Depends(current_user),
                  db: Session = Depends(get_db)):
    card = db.get(models.Card, body.card_id)
    if not card:
        raise HTTPException(404, "Card not found")
    _accessible_deck(db, card.deck_id, user)  # authz

    rating = min(4, max(1, body.rating))
    combo = min(50, max(0, body.combo))  # server-side cap on client-reported combo

    db.add(models.ReviewLog(
        user_id=user.id, card_id=card.id, mode=body.mode,
        rating=rating, correct=body.correct, ms_taken=body.ms_taken))

    # FSRS scheduling if the deck opted in
    next_due = None
    deck = db.get(models.Deck, card.deck_id)
    if deck and deck.smart_review:
        review = db.scalar(select(models.CardReview).where(
            models.CardReview.user_id == user.id, models.CardReview.card_id == card.id))
        if not review:
            review = models.CardReview(user_id=user.id, card_id=card.id)
            db.add(review)
            db.flush()
        fsrs.schedule(review, rating)
        next_due = review.due

    # XP + streak + daily bonus
    amount = xp.review_xp(body.correct, combo, body.mode, body.ms_taken)
    xp.award(db, user.id, amount, "review", {"card_id": card.id, "mode": body.mode})
    streak, first_today = xp.touch_streak(db, user.id)
    if first_today:
        amount += xp.award(db, user.id, xp.XP_DAILY_FIRST, "daily_first")

    new_achievements = xp.check_review_achievements(db, user.id)
    db.commit()

    txp = xp.total_xp(db, user.id)
    level, progress = xp.level_from_xp(txp)
    return schemas.ReviewOut(
        xp_awarded=amount, total_xp=txp, level=level, level_progress=progress,
        new_achievements=new_achievements, next_due=next_due)


@router.post("/session/complete", response_model=schemas.ReviewOut)
def complete_session(body: schemas.SessionCompleteIn,
                     user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    _accessible_deck(db, body.deck_id, user)
    amount = xp.award(db, user.id, xp.XP_DECK_COMPLETE, "deck_complete", {"deck_id": body.deck_id})

    new_achievements = []
    if body.cards_seen >= 20 and body.correct == body.cards_seen:
        r = xp.grant(db, user.id, "perfectionist")
        if r:
            new_achievements.append(r)
    db.commit()

    txp = xp.total_xp(db, user.id)
    level, progress = xp.level_from_xp(txp)
    return schemas.ReviewOut(
        xp_awarded=amount, total_xp=txp, level=level, level_progress=progress,
        new_achievements=new_achievements)
