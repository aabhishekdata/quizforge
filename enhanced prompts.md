This is a nice evolution — from "quiz the document" to "build a mental model of the subject." The key architectural change is that deep-knowledge cards can't be generated from isolated chunks, because first principles and cross-concept connections live between chunks. So I'd restructure the pipeline around a two-pass design, plus an enriched card schema.
Enhanced generation principle
Pass 0 — Build a subject skeleton (new step, runs once per document)
Before chunk-level generation, send the document outline (headings + first sentences, or a map-reduce summary) to the LLM and ask it to produce a concept map:
json{
  "subject": "Event Streaming Architectures",
  "first_principles": [
    {
      "id": "fp1",
      "principle": "Decoupling producers from consumers in time and space",
      "why_it_matters": "Everything else (partitions, offsets, replay) exists to serve this"
    }
  ],
  "core_concepts": [
    {
      "id": "c1",
      "name": "Partitioning",
      "depends_on": ["c0"],
      "maps_to_principle": "fp1",
      "common_misconceptions": ["Partitions guarantee global ordering"]
    }
  ]
}
This skeleton is cached and injected into every chunk-level prompt as context. That's what lets a card generated from page 14 reference a concept introduced on page 3.
Pass 1 — Chunk-level generation with an enriched schema
json{
  "cards": [
    {
      "front": "term or question",
      "back": "concise answer",
      "card_type": "recall | why | application | contrast | derivation",
      "difficulty": "easy | medium | hard",
      "first_principle": "The fundamental idea this card connects to (from skeleton, or null)",
      "elaboration": "2-3 sentences: WHY this is true, not just WHAT is true",
      "connections": ["concept_id_1", "concept_id_2"],
      "misconception_note": "What people commonly get wrong here, or null",
      "real_world_example": "One concrete application outside the document, or null",
      "mcq": {
        "choices": ["A", "B", "C", "D"],
        "answer_index": 0,
        "distractor_rationale": ["why each wrong answer is tempting"]
      },
      "external_ref": {
        "type": "wikipedia | official_docs | search_query",
        "value": "..."
      },
      "source": { "chunk": 3, "page": 14 }
    }
  ]
}
Updated prompt rules (the core instruction block)

Distribute card types roughly: 30% recall, 25% why/mechanism ("why does X work this way?"), 20% application ("given scenario Y, what would you do?"), 15% contrast ("how does X differ from Z and when would you pick each?"), 10% derivation ("derive/reconstruct X from first principles").
Every medium/hard card must fill elaboration — the back answers what, the elaboration answers why. This is what converts flashcards into understanding.
MCQ distractors must come from the common_misconceptions in the skeleton where available, not random plausible-sounding options. Misconception-based distractors are dramatically better for learning.
real_world_example should deliberately go outside the document — this is your "deep knowledge beyond the material" lever.
Cards may reference concepts from other chunks via the skeleton, enabling synthesis cards like "How does partitioning (§2) interact with consumer groups (§5)?"

The links problem — one important caution
Don't let the LLM emit free-form URLs. Models hallucinate links constantly, and a flashcard with a dead or wrong link is worse than no link. Three safe options, in order of preference:

Constrained patterns: only allow https://en.wikipedia.org/wiki/{Title} or a whitelist of official-docs domains, then validate with a cheap HEAD request in your cleaning step and drop failures.
Search queries instead of URLs: have the model emit "search_query": "Kafka consumer group rebalancing explained" and render it as a search link client-side. Never breaks.
Post-hoc enrichment: a separate step that takes the card's key term and resolves it against Wikipedia's API — deterministic, no hallucination.

The external_ref.type field in the schema above supports all three.
Updated validation step
Your existing cleaning step gains a few checks: drop cards whose connections reference concept IDs not in the skeleton; verify distractor_rationale length matches choices; HEAD-check or pattern-check external refs; and — new and worth doing — cross-chunk dedup, since richer prompts make near-duplicate cards from adjacent chunks more likely (embedding similarity > ~0.9 → keep the higher-difficulty one).
Storage upside
Because cards now carry connections and first_principle, your deck is implicitly a knowledge graph. That unlocks two features cheaply later: a "prerequisite ordering" study mode (study c0 before c1), and a concept-coverage report showing which core concepts have zero cards — a signal to regenerate for that gap.
The cost tradeoff is real: Pass 0 adds one extra LLM call per document, and richer cards mean ~2-3x output tokens per chunk. If cost matters, make the enrichment fields (elaboration, real_world_example) optional for easy cards and mandatory only for medium/hard — that's where the pedagogical payoff concentrates anyway.
Want me to draft the actual updated prompt template (system + user message) for Pass 0 and Pass 1 that you can drop into QuizForge?yes share here only - do not update the appIdentified request to share prompt templates directlyIdentified request to share prompt templates directlyThe user is asking for the actual prompt templates for Pass 0 and Pass 1 to share directly in the conversation, including both system and user message components. They want these to be reasonably complete and are fine with code blocks for the templates themselves.DoneHere are both prompt templates, ready to drop into your provider-agnostic prompt layer (they work as-is for Anthropic, OpenAI, and DeepSeek).
Pass 0 — Subject Skeleton
System prompt:
You are a curriculum designer and subject-matter expert. Your job is to read a
document outline and reconstruct the SUBJECT's underlying structure — the first
principles, core concepts, dependencies, and common misconceptions — not merely
summarize the document.

Rules:
- Think like someone teaching this subject from scratch, not someone indexing a file.
- First principles are the small set of fundamental ideas from which everything
  else in the subject can be derived or explained. Aim for 2-6, never more than 8.
- Core concepts are the teachable units. Each must map to exactly one first
  principle and list its prerequisite concepts (by id). Aim for 8-20.
- Misconceptions must be things a real learner plausibly believes, specific
  enough to later serve as MCQ distractors. Avoid generic errors like
  "confusing X with Y" unless you state what the confusion actually is.
- Dependency graph must be acyclic. c0-style foundational concepts have
  "depends_on": [].
- Respond with ONLY valid JSON. No markdown fences, no preamble, no commentary.
User prompt template:
Document title: {{doc_title}}
Document type: {{doc_type}}

Document outline (headings and lead sentences):
---
{{outline_text}}
---

Produce the subject skeleton as JSON in exactly this shape:

{
  "subject": "string — the subject this document teaches, not the document's name",
  "audience_level": "beginner | intermediate | advanced",
  "first_principles": [
    {
      "id": "fp1",
      "principle": "string",
      "why_it_matters": "string — what breaks or becomes inexplicable without it"
    }
  ],
  "core_concepts": [
    {
      "id": "c1",
      "name": "string",
      "one_line_definition": "string",
      "depends_on": ["c0"],
      "maps_to_principle": "fp1",
      "common_misconceptions": ["specific wrong belief a learner might hold"]
    }
  ]
}
Pass 1 — Card Generation (per chunk)
System prompt:
You are an expert tutor creating spaced-repetition flashcards. Your goal is to
build DEEP UNDERSTANDING of the subject, using this document chunk as the
primary source. Test understanding of the material — never trivia about the
document itself (no "according to page 4..." or "the author states..." cards).

You are given a SUBJECT SKELETON (first principles, concept graph,
misconceptions) covering the whole document. Use it to:
- connect this chunk's cards to first principles,
- reference concepts from OTHER parts of the document when it deepens a card,
- source MCQ distractors from listed misconceptions whenever one fits.

CARD TYPE DISTRIBUTION (approximate, across the cards you generate):
- 30% recall      — definitions, facts, terminology
- 25% why         — mechanism, causation: "why does X behave this way?"
- 20% application — a concrete scenario requiring the concept to resolve
- 15% contrast    — "how does X differ from Y, and when do you choose each?"
- 10% derivation  — reconstruct X from first principles

HARD RULES:
1. Generate at most {{cards_per_chunk}} cards. Fewer is fine if the chunk is thin.
   Never pad with weak cards.
2. Roughly half the cards must include an "mcq" object; the rest set "mcq": null.
3. MCQ: exactly 4 choices, exactly one correct, answer_index is its 0-based
   position. Distractors must be plausible — prefer skeleton misconceptions.
   Provide "distractor_rationale" for the 3 wrong choices in choice order
   (skip the correct one).
4. "front" under 200 characters. "back" under 400 characters — concise answer
   only. Depth goes in "elaboration".
5. "elaboration" is REQUIRED for medium and hard cards: 2-3 sentences explaining
   WHY the answer is true, its mechanism, or its consequence. May be null for
   easy cards.
6. "real_world_example" must come from OUTSIDE the document — a genuine
   application in industry, daily life, or another field. Include it on at
   least one-third of cards; null otherwise.
7. "connections" lists concept ids from the skeleton this card touches
   (including cross-chunk concepts). Use only ids that exist in the skeleton.
8. "first_principle" is the fp id this card ultimately serves, or null if
   genuinely none.
9. "misconception_note" states what learners commonly get wrong here, or null.
10. "external_ref": either
    {"type": "wikipedia", "value": "Exact_Wikipedia_Article_Title"} or
    {"type": "search_query", "value": "a good search phrase"} or null.
    NEVER output a raw URL. Never invent a Wikipedia title you are not
    confident exists; prefer search_query when unsure.
11. Do not duplicate ideas already covered by PREVIOUSLY GENERATED CARD FRONTS
    (provided below). Approach shared concepts from a new angle or skip them.
12. Respond with ONLY valid JSON. No markdown fences, no preamble.
User prompt template:
SUBJECT SKELETON:
{{skeleton_json}}

PREVIOUSLY GENERATED CARD FRONTS (avoid duplicating these):
{{previous_fronts_list}}

DOCUMENT CHUNK ({{chunk_index}} of {{total_chunks}}, pages {{page_range}}):
---
{{chunk_text}}
---

Generate the cards as JSON in exactly this shape:

{
  "cards": [
    {
      "front": "string",
      "back": "string",
      "card_type": "recall | why | application | contrast | derivation",
      "difficulty": "easy | medium | hard",
      "first_principle": "fp id or null",
      "elaboration": "string or null",
      "connections": ["c1", "c4"],
      "misconception_note": "string or null",
      "real_world_example": "string or null",
      "mcq": {
        "choices": ["A", "B", "C", "D"],
        "answer_index": 0,
        "distractor_rationale": ["why wrong choice 1 tempts", "why wrong choice 2 tempts", "why wrong choice 3 tempts"]
      },
      "external_ref": {"type": "wikipedia | search_query", "value": "string"},
      "source": {"chunk": {{chunk_index}}, "page": null}
    }
  ]
}
A few implementation notes on the template variables:
{{previous_fronts_list}} — pass just the front strings from cards generated so far (or the last ~50 if the deck gets large). This is your cheapest dedup lever and works even before the embedding-based dedup in validation. For chunk 1, pass "(none yet)".
{{outline_text}} for Pass 0 — if the document has no headings (common with scanned PDFs), fall back to: first 2 sentences of each chunk, concatenated with chunk numbers. That's usually enough signal for a skeleton. Cap the whole thing at ~4-6k tokens; if it exceeds that, take every other chunk's lead sentences.
Skeleton injection size — the skeleton JSON typically lands at 500-1,500 tokens, so injecting it into every Pass 1 call is cheap relative to the chunk text. If you're using Anthropic, put the skeleton and system prompt in a cacheable prefix (prompt caching) so you only pay full price once per document — the per-chunk marginal cost drops substantially.
Validation hooks these prompts assume — your cleaning step should enforce: distractor_rationale has exactly 3 entries when mcq is present; connections ids exist in the skeleton (drop unknown ids, keep the card); wikipedia type refs get resolved via the Wikipedia API opensearch endpoint and downgraded to search_query on miss; and inject the real page number into source.page from your chunk metadata since the model can't know it reliably.
One behavioral note worth testing early: rule 1 ("fewer is fine, never pad") plus the type distribution sometimes makes weaker models under-generate on dense chunks. If you see that with DeepSeek, soften rule 1 to "generate between {{min_cards}} and {{cards_per_chunk}} cards" and let validation do the pruning instead.