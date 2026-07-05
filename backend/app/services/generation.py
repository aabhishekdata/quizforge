"""Generate flashcards + MCQs from text chunks via a configured LLM provider."""
import json
import re

import anthropic
from openai import OpenAI

from ..config import settings

PASS0_SYSTEM = """You are a curriculum designer and subject-matter expert. Your job is to read a
document outline and reconstruct the SUBJECT's underlying structure: the first
principles, core concepts, dependencies, and common misconceptions, not merely
summarize the document.

Rules:
- Think like someone teaching this subject from scratch, not someone indexing a file.
- First principles are the small set of fundamental ideas from which everything
  else in the subject can be derived or explained. Aim for 2-6, never more than 8.
- Core concepts are the teachable units. Each must map to exactly one first
  principle and list its prerequisite concepts by id. Aim for 8-20.
- Misconceptions must be things a real learner plausibly believes, specific
  enough to later serve as MCQ distractors.
- Dependency graph must be acyclic. c0-style foundational concepts have
  "depends_on": [].
- Respond with ONLY valid JSON. No markdown fences, no preamble, no commentary.
- Use compact JSON strings. Do not put literal newline characters inside string values."""

PASS1_SYSTEM = """You are an expert tutor creating spaced-repetition flashcards. Your goal is to
build DEEP UNDERSTANDING of the subject, using this document chunk as the
primary source. Test understanding of the material, never trivia about the
document itself.

You are given a SUBJECT SKELETON covering the whole document. Use it to:
- connect this chunk's cards to first principles,
- reference concepts from other parts of the document when it deepens a card,
- source MCQ distractors from listed misconceptions whenever one fits.

CARD TYPE DISTRIBUTION, approximate across the cards you generate:
- 30% recall: definitions, facts, terminology
- 25% why: mechanism, causation
- 20% application: a concrete scenario requiring the concept to resolve
- 15% contrast: how X differs from Y, and when to choose each
- 10% derivation: reconstruct X from first principles

HARD RULES:
1. Generate at most the requested number of cards. Fewer is fine if the chunk is thin.
   Never pad with weak cards.
2. Roughly half the cards must include an "mcq" object; the rest set "mcq": null.
3. MCQ: exactly 4 choices, exactly one correct, answer_index is its 0-based
   position. Distractors must be plausible; prefer skeleton misconceptions.
   Provide "distractor_rationale" for the 3 wrong choices in choice order
   (skip the correct one).
4. "front" under 200 characters. "back" under 400 characters; concise answer only.
   Depth goes in "elaboration".
5. "elaboration" is REQUIRED for medium and hard cards: 2-3 sentences explaining
   WHY the answer is true, its mechanism, or its consequence. May be null for easy cards.
6. "real_world_example" must come from outside the document. Include it on at
   least one-third of cards; null otherwise.
7. "connections" lists concept ids from the skeleton this card touches.
   Use only ids that exist in the skeleton.
8. "first_principle" is the fp id this card ultimately serves, or null if genuinely none.
9. "misconception_note" states what learners commonly get wrong here, or null.
10. Do not output links, URLs, citations, or external references. Focus only on
    the card, first principle, elaboration, misconceptions, examples, and
    concept connections.
11. Do not duplicate ideas already covered by PREVIOUSLY GENERATED CARD FRONTS.
12. Respond with ONLY valid JSON. No markdown fences, no preamble.
13. Use compact JSON strings. Do not put literal newline characters inside string values."""

LEGACY_SYSTEM = """You generate study flashcards from educational material.
Respond ONLY with a JSON object, no prose, no markdown fences. Schema:
{
  "cards": [
    {
      "front": "term or question (concise)",
      "back": "definition or answer (1-3 sentences)",
      "difficulty": "easy" | "medium" | "hard",
      "mcq": {"choices": ["A", "B", "C", "D"], "answer_index": 0} | null
    }
  ]
}
Rules:
- Cards must test understanding of the MATERIAL, not trivia about the document.
- Fronts must be unambiguous without seeing the source.
- For roughly half the cards, include an "mcq" with 4 choices and plausible
  distractors drawn from the same material. Others set "mcq": null.
- No duplicate or near-duplicate cards.
- All content in English."""


def _legacy_user_prompt(chunk_text: str, source_label: str, n_cards: int) -> str:
    return (
        f"Generate up to {n_cards} flashcards from this material "
        f"(source: {source_label}). Fewer is fine if the material is thin.\n\n"
        f"<material>\n{chunk_text}\n</material>"
    )


def _anthropic_completion(system: str, prompt: str, high_quality: bool, max_tokens: int = 4000) -> str:
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is required when GENERATION_PROVIDER=anthropic.")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    model = settings.generation_model_hq if high_quality else settings.generation_model

    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")


def _openai_compatible_completion(
    *,
    api_key: str,
    base_url: str | None,
    model: str,
    system: str,
    prompt: str,
    max_tokens: int = 4000,
    temperature: float | None = 0.2,
    reasoning_effort: str | None = None,
    extra_body: dict | None = None,
) -> str:
    if not api_key:
        raise ValueError(f"API key is required for model {model}.")
    client = OpenAI(api_key=api_key, base_url=base_url)
    params = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    if temperature is not None:
        params["temperature"] = temperature
    if reasoning_effort:
        params["reasoning_effort"] = reasoning_effort
    if extra_body:
        params["extra_body"] = extra_body
    response = client.chat.completions.create(
        **params,
    )
    return response.choices[0].message.content or ""


def _openai_completion(system: str, prompt: str, high_quality: bool, max_tokens: int = 4000) -> str:
    model = settings.openai_generation_model_hq if high_quality else settings.openai_generation_model
    return _openai_compatible_completion(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=model,
        system=system,
        prompt=prompt,
        temperature=0.2,
        max_tokens=max_tokens,
    )


def _deepseek_completion(system: str, prompt: str, high_quality: bool, max_tokens: int = 4000) -> str:
    model = settings.deepseek_generation_model_hq if high_quality else settings.deepseek_generation_model
    effort = settings.deepseek_reasoning_effort.strip().lower()
    if effort not in {"high", "max"}:
        effort = "max"
    extra_body = {"thinking": {"type": "enabled"}} if settings.deepseek_thinking_enabled else None
    return _openai_compatible_completion(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=model,
        system=system,
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=None,
        reasoning_effort=effort,
        extra_body=extra_body,
    )


def _completion(system: str, prompt: str, high_quality: bool, max_tokens: int = 4000) -> str:
    provider = settings.generation_provider.strip().lower()
    if provider == "anthropic":
        return _anthropic_completion(system, prompt, high_quality, max_tokens)
    if provider == "openai":
        return _openai_completion(system, prompt, high_quality, max_tokens)
    if provider == "deepseek":
        return _deepseek_completion(system, prompt, high_quality, max_tokens)
    raise ValueError(
        "Unsupported GENERATION_PROVIDER. Use one of: anthropic, openai, deepseek."
    )


def _json_from_model(raw: str) -> dict:
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    candidates = [raw]
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        candidates.append(raw[start:end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            try:
                return json.loads(_escape_control_chars_in_strings(candidate))
            except json.JSONDecodeError:
                pass
    raise json.JSONDecodeError("No valid JSON object found", raw, 0)


def _escape_control_chars_in_strings(raw: str) -> str:
    """Repair common model JSON mistakes: literal newlines/tabs inside strings."""
    out = []
    in_string = False
    escaped = False
    for ch in raw:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\" and in_string:
            out.append(ch)
            escaped = True
            continue
        if ch == '"':
            out.append(ch)
            in_string = not in_string
            continue
        if in_string and ch == "\n":
            out.append("\\n")
            continue
        if in_string and ch == "\r":
            out.append("\\r")
            continue
        if in_string and ch == "\t":
            out.append("\\t")
            continue
        out.append(ch)
    return "".join(out)


def _clean_text(value, max_len: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:max_len]


def _optional_clean_text(value, max_len: int) -> str | None:
    cleaned = _clean_text(value, max_len)
    return cleaned or None


def _lead_sentences(text: str, limit: int = 2) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:limit])[:700]


def build_document_outline(sections: list[tuple[str, str]], max_chars: int = 14000) -> str:
    lines = []
    for i, (label, text) in enumerate(sections, start=1):
        lead = _lead_sentences(text)
        if lead:
            lines.append(f"{i}. {label}: {lead}")
    outline = "\n".join(lines)
    if len(outline) <= max_chars:
        return outline
    sampled = lines[::2]
    outline = "\n".join(sampled)
    return outline[:max_chars]


def _skeleton_user_prompt(doc_title: str, doc_type: str, outline_text: str) -> str:
    return f"""Document title: {doc_title}
Document type: {doc_type}

Document outline (headings and lead sentences):
---
{outline_text}
---

Produce the subject skeleton as JSON in exactly this shape:

{{
  "subject": "string - the subject this document teaches, not the document's name",
  "audience_level": "beginner | intermediate | advanced",
  "first_principles": [
    {{
      "id": "fp1",
      "principle": "string",
      "why_it_matters": "string - what breaks or becomes inexplicable without it"
    }}
  ],
  "core_concepts": [
    {{
      "id": "c1",
      "name": "string",
      "one_line_definition": "string",
      "depends_on": ["c0"],
      "maps_to_principle": "fp1",
      "common_misconceptions": ["specific wrong belief a learner might hold"]
    }}
  ]
}}"""


def _clean_skeleton(data: dict) -> dict:
    first_principles = []
    fp_ids = set()
    for i, fp in enumerate(data.get("first_principles") or [], start=1):
        if not isinstance(fp, dict):
            continue
        fp_id = str(fp.get("id") or f"fp{i}")[:20]
        principle = _clean_text(fp.get("principle"), 300)
        if not principle:
            continue
        fp_ids.add(fp_id)
        first_principles.append({
            "id": fp_id,
            "principle": principle,
            "why_it_matters": _clean_text(fp.get("why_it_matters"), 600),
        })

    concepts = []
    concept_ids = set()
    raw_concepts = [c for c in (data.get("core_concepts") or []) if isinstance(c, dict)]
    for i, concept in enumerate(raw_concepts, start=1):
        concept_id = str(concept.get("id") or f"c{i}")[:20]
        name = _clean_text(concept.get("name"), 120)
        if not name:
            continue
        concept_ids.add(concept_id)
        concepts.append({
            "id": concept_id,
            "name": name,
            "one_line_definition": _clean_text(concept.get("one_line_definition"), 400),
            "depends_on": [str(x)[:20] for x in (concept.get("depends_on") or []) if isinstance(x, str)],
            "maps_to_principle": str(concept.get("maps_to_principle") or "").strip()[:20],
            "common_misconceptions": [
                _clean_text(x, 300)
                for x in (concept.get("common_misconceptions") or [])
                if _clean_text(x, 300)
            ][:5],
        })

    for concept in concepts:
        concept["depends_on"] = [x for x in concept["depends_on"] if x in concept_ids and x != concept["id"]]
        if concept["maps_to_principle"] not in fp_ids:
            concept["maps_to_principle"] = first_principles[0]["id"] if first_principles else None

    return {
        "subject": _clean_text(data.get("subject") or "Untitled subject", 200),
        "audience_level": _clean_text(data.get("audience_level") or "intermediate", 20),
        "first_principles": first_principles[:8],
        "core_concepts": concepts[:24],
    }


def build_subject_skeleton(
    doc_title: str,
    doc_type: str,
    sections: list[tuple[str, str]],
    high_quality: bool = False,
) -> dict:
    outline = build_document_outline(sections)
    raw = _completion(
        PASS0_SYSTEM,
        _skeleton_user_prompt(doc_title, doc_type, outline),
        high_quality,
        max_tokens=3500,
    )
    try:
        return _clean_skeleton(_json_from_model(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return _clean_skeleton({
            "subject": doc_title,
            "audience_level": "intermediate",
            "first_principles": [],
            "core_concepts": [],
        })


def _format_previous_fronts(previous_fronts: list[str] | None) -> str:
    fronts = [f.strip() for f in (previous_fronts or []) if f.strip()]
    if not fronts:
        return "(none yet)"
    return "\n".join(f"- {front[:220]}" for front in fronts[-60:])


def _chunk_user_prompt(
    chunk_text: str,
    source_label: str,
    n_cards: int,
    skeleton: dict | None,
    previous_fronts: list[str] | None,
    chunk_index: int,
    total_chunks: int,
) -> str:
    skeleton_json = json.dumps(skeleton or {}, ensure_ascii=False, indent=2)
    return f"""SUBJECT SKELETON:
{skeleton_json}

PREVIOUSLY GENERATED CARD FRONTS (avoid duplicating these):
{_format_previous_fronts(previous_fronts)}

DOCUMENT CHUNK ({chunk_index} of {total_chunks}, source {source_label}):
---
{chunk_text}
---

Generate at most {n_cards} cards as JSON in exactly this shape:

{{
  "cards": [
    {{
      "front": "string",
      "back": "string",
      "card_type": "recall | why | application | contrast | derivation",
      "difficulty": "easy | medium | hard",
      "first_principle": "fp id or null",
      "elaboration": "string or null",
      "connections": ["c1", "c4"],
      "misconception_note": "string or null",
      "real_world_example": "string or null",
      "mcq": {{
        "choices": ["A", "B", "C", "D"],
        "answer_index": 0,
        "distractor_rationale": ["why wrong choice 1 tempts", "why wrong choice 2 tempts", "why wrong choice 3 tempts"]
      }},
      "source": {{"chunk": {chunk_index}, "page": null}}
    }}
  ]
}}"""


def _valid_ids(skeleton: dict | None) -> tuple[set[str], set[str]]:
    skeleton = skeleton or {}
    fp_ids = {str(fp.get("id")) for fp in skeleton.get("first_principles", []) if isinstance(fp, dict) and fp.get("id")}
    concept_ids = {str(c.get("id")) for c in skeleton.get("core_concepts", []) if isinstance(c, dict) and c.get("id")}
    return fp_ids, concept_ids


def _normalize_front(front: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", front.lower()).strip()


def _clean_cards(
    cards: list[dict],
    source_label: str,
    skeleton: dict | None,
    previous_fronts: list[str] | None,
) -> list[dict]:
    fp_ids, concept_ids = _valid_ids(skeleton)
    seen = {_normalize_front(f) for f in (previous_fronts or [])}
    cleaned = []
    card_types = {"recall", "why", "application", "contrast", "derivation"}
    difficulties = {"easy", "medium", "hard"}

    for c in cards:
        if not isinstance(c, dict):
            continue
        front, back = _clean_text(c.get("front"), 1000), _clean_text(c.get("back"), 2000)
        if not front or not back:
            continue
        normalized = _normalize_front(front)
        if normalized in seen:
            continue
        seen.add(normalized)

        card_type = c.get("card_type") if c.get("card_type") in card_types else "recall"
        difficulty = c.get("difficulty") if c.get("difficulty") in difficulties else "medium"
        first_principle = c.get("first_principle")
        if first_principle not in fp_ids:
            first_principle = None
        connections = [
            x for x in (c.get("connections") or [])
            if isinstance(x, str) and x in concept_ids
        ][:8]

        mcq = c.get("mcq")
        if mcq:
            choices = [_clean_text(x, 500) for x in (mcq.get("choices") or []) if _clean_text(x, 500)]
            answer_index = mcq.get("answer_index")
            if len(choices) == 4 and isinstance(answer_index, int) and 0 <= answer_index < 4:
                rationale = [
                    _clean_text(x, 400)
                    for x in (mcq.get("distractor_rationale") or [])
                    if _clean_text(x, 400)
                ]
                mcq = {
                    "choices": choices,
                    "answer_index": answer_index,
                    "distractor_rationale": rationale[:3] if len(rationale) == 3 else [],
                }
            else:
                mcq = None

        meta = {
            "first_principle": first_principle,
            "elaboration": _optional_clean_text(c.get("elaboration"), 1200),
            "connections": connections,
            "misconception_note": _optional_clean_text(c.get("misconception_note"), 800),
            "real_world_example": _optional_clean_text(c.get("real_world_example"), 800),
            "source": c.get("source") if isinstance(c.get("source"), dict) else None,
        }

        cleaned.append({
            "front": front,
            "back": back,
            "difficulty": difficulty,
            "card_type": card_type,
            "learning_meta": meta,
            "mcq_options": mcq,
            "source_ref": source_label[:255],
        })
    return cleaned


def generate_cards_for_chunk(
    chunk_text: str,
    source_label: str,
    n_cards: int,
    high_quality: bool = False,
    skeleton: dict | None = None,
    previous_fronts: list[str] | None = None,
    chunk_index: int = 1,
    total_chunks: int = 1,
) -> list[dict]:
    if skeleton is None:
        raw = _completion(
            LEGACY_SYSTEM,
            _legacy_user_prompt(chunk_text, source_label, n_cards),
            high_quality,
        )
    else:
        raw = _completion(
            PASS1_SYSTEM,
            _chunk_user_prompt(
                chunk_text, source_label, n_cards, skeleton, previous_fronts,
                chunk_index, total_chunks,
            ),
            high_quality,
            max_tokens=16000,
        )
    try:
        data = _json_from_model(raw)
        cards = data.get("cards", [])
    except json.JSONDecodeError:
        return []

    return _clean_cards(cards, source_label, skeleton, previous_fronts)
