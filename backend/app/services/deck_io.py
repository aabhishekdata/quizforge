import csv
import io
import json
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from .. import models


FORMAT_VERSION = "quizforge.deck.v1"
DIFFICULTIES = {"easy", "medium", "hard"}
CARD_TYPES = {"recall", "why", "application", "contrast", "derivation"}
MAX_CARDS = 5000


@dataclass
class ImportedDeck:
    title: str
    description: str
    cards: list[dict[str, Any]]


def deck_to_payload(deck: models.Deck, cards: list[models.Card]) -> dict[str, Any]:
    return {
        "format": FORMAT_VERSION,
        "deck": {
            "title": deck.title,
            "description": deck.description,
            "smart_review": deck.smart_review,
        },
        "cards": [
            {
                "front": card.front,
                "back": card.back,
                "difficulty": card.difficulty,
                "card_type": card.card_type,
                "learning_meta": card.learning_meta,
                "mcq_options": card.mcq_options,
                "source_ref": card.source_ref,
            }
            for card in cards
        ],
    }


def deck_to_json(deck: models.Deck, cards: list[models.Card]) -> str:
    return json.dumps(deck_to_payload(deck, cards), ensure_ascii=False, indent=2)


def deck_to_csv(cards: list[models.Card]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "front",
            "back",
            "difficulty",
            "card_type",
            "source_ref",
            "learning_meta",
            "mcq_options",
        ],
    )
    writer.writeheader()
    for card in cards:
        writer.writerow({
            "front": card.front,
            "back": card.back,
            "difficulty": card.difficulty,
            "card_type": card.card_type,
            "source_ref": card.source_ref or "",
            "learning_meta": _dump_optional_json(card.learning_meta),
            "mcq_options": _dump_optional_json(card.mcq_options),
        })
    return output.getvalue()


def parse_import(filename: str, data: bytes, title: str | None = None) -> ImportedDeck:
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    if ext == "json":
        return parse_json_deck(data, title=title)
    if ext == "csv":
        return parse_csv_deck(data, fallback_title=title or _title_from_filename(filename))
    raise HTTPException(400, "Unsupported deck import type. Use .json or .csv")


def parse_json_deck(data: bytes, title: str | None = None) -> ImportedDeck:
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(400, "Invalid JSON deck file")

    if not isinstance(payload, dict):
        raise HTTPException(400, "JSON deck must be an object")

    deck_data = payload.get("deck") if isinstance(payload.get("deck"), dict) else payload
    cards_data = payload.get("cards")
    if not isinstance(cards_data, list):
        raise HTTPException(400, "JSON deck must include a cards array")

    imported_title = _clean_text(title or deck_data.get("title") or "Imported deck", 200)
    description = _clean_text(deck_data.get("description") or "", 5000, required=False)
    return ImportedDeck(
        title=imported_title,
        description=description,
        cards=_normalize_cards(cards_data),
    )


def parse_csv_deck(data: bytes, fallback_title: str) -> ImportedDeck:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV deck must be UTF-8 encoded")

    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = list(reader)
    if not rows:
        raise HTTPException(400, "CSV deck is empty")

    normalized_fields = {(_field_name(name)): name for name in (reader.fieldnames or [])}
    front_key = normalized_fields.get("front") or normalized_fields.get("question") or normalized_fields.get("term")
    back_key = normalized_fields.get("back") or normalized_fields.get("answer") or normalized_fields.get("definition")

    if not front_key or not back_key:
        raise HTTPException(400, "CSV deck needs front/back columns, or question/answer columns")

    cards = []
    for row in rows:
        card = {
            "front": row.get(front_key),
            "back": row.get(back_key),
            "difficulty": _row_value(row, normalized_fields, "difficulty"),
            "card_type": _row_value(row, normalized_fields, "card_type"),
            "source_ref": _row_value(row, normalized_fields, "source_ref"),
            "learning_meta": _parse_json_field(_row_value(row, normalized_fields, "learning_meta")),
            "mcq_options": _parse_json_field(_row_value(row, normalized_fields, "mcq_options")),
        }
        cards.append(card)

    return ImportedDeck(
        title=_clean_text(fallback_title or "Imported deck", 200),
        description="Imported from CSV",
        cards=_normalize_cards(cards),
    )


def _normalize_cards(raw_cards: list[Any]) -> list[dict[str, Any]]:
    if len(raw_cards) > MAX_CARDS:
        raise HTTPException(400, f"Deck imports are limited to {MAX_CARDS} cards")

    cards = []
    for raw in raw_cards:
        if not isinstance(raw, dict):
            continue
        front = _clean_text(raw.get("front"), 1000, required=False)
        back = _clean_text(raw.get("back"), 2000, required=False)
        if not front or not back:
            continue

        difficulty = raw.get("difficulty") if raw.get("difficulty") in DIFFICULTIES else "medium"
        card_type = raw.get("card_type") if raw.get("card_type") in CARD_TYPES else "recall"
        cards.append({
            "front": front,
            "back": back,
            "difficulty": difficulty,
            "card_type": card_type,
            "learning_meta": raw.get("learning_meta") if isinstance(raw.get("learning_meta"), dict) else None,
            "mcq_options": _normalize_mcq(raw.get("mcq_options")),
            "source_ref": _clean_text(raw.get("source_ref"), 255, required=False) or None,
        })

    if not cards:
        raise HTTPException(400, "No valid cards found in import")
    return cards


def _normalize_mcq(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    choices = value.get("choices")
    answer_index = value.get("answer_index")
    if not isinstance(choices, list) or not isinstance(answer_index, int):
        return None
    clean_choices = [_clean_text(choice, 500, required=False) for choice in choices]
    clean_choices = [choice for choice in clean_choices if choice]
    if len(clean_choices) < 2 or not 0 <= answer_index < len(clean_choices):
        return None
    return {
        "choices": clean_choices[:8],
        "answer_index": answer_index,
        "distractor_rationale": value.get("distractor_rationale")
        if isinstance(value.get("distractor_rationale"), list)
        else [],
    }


def _clean_text(value: Any, limit: int, required: bool = True) -> str:
    if value is None:
        if required:
            raise HTTPException(400, "Required text field is missing")
        return ""
    cleaned = str(value).strip()
    if not cleaned and required:
        raise HTTPException(400, "Required text field is empty")
    return cleaned[:limit]


def _dump_optional_json(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse_json_field(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _field_name(value: str | None) -> str:
    return (value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _row_value(row: dict[str, str], fields: dict[str, str], normalized_name: str) -> str | None:
    key = fields.get(normalized_name)
    return row.get(key) if key else None


def _title_from_filename(filename: str) -> str:
    stem = (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
    return stem.replace("_", " ").replace("-", " ").strip().title() or "Imported deck"
