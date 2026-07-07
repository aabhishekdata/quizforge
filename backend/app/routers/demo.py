from fastapi import APIRouter, HTTPException, Query

from ..services.demo_deck import DEMO_CARDS, demo_deck_out

router = APIRouter(prefix="/api/demo", tags=["demo"])


def _require_demo_deck(deck_id: str):
    if deck_id != "mental-models":
        raise HTTPException(404, "Demo deck not found")


@router.get("/decks/mental-models")
def get_demo_deck():
    return demo_deck_out()


@router.get("/decks/{deck_id}/cards")
def list_demo_cards(deck_id: str):
    _require_demo_deck(deck_id)
    return DEMO_CARDS


@router.get("/study/{deck_id}/session")
def demo_study_session(
    deck_id: str,
    mode: str = Query("flashcard"),
    limit: int = Query(20, ge=1, le=50),
):
    _require_demo_deck(deck_id)
    cards = [card for card in DEMO_CARDS if mode != "mcq" or card.get("mcq_options")]
    if mode not in {"flashcard", "mcq", "type"}:
        mode = "flashcard"
    return cards[:limit]
