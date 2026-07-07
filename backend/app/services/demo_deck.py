from datetime import datetime


DEMO_DECK = {
    "id": "mental-models",
    "title": "Mental Models",
    "description": "A small demo deck for practicing useful thinking tools.",
    "owner_id": 0,
    "owner_username": "demo",
    "is_shared_with_me": False,
    "subject_id": None,
    "subject_name": "Thinking Tools",
    "smart_review": False,
    "due_count": 0,
    "created_at": datetime(2026, 1, 1),
}


DEMO_CARDS = [
    {
        "id": 1,
        "front": "What is inversion?",
        "back": "Inversion is solving a problem by asking what would cause failure, then avoiding those causes.",
        "difficulty": "easy",
        "card_type": "recall",
        "source_ref": "mental models",
        "mcq_options": {
            "choices": [
                "Working backward from failure modes",
                "Choosing the most popular answer",
                "Ignoring unlikely risks",
                "Repeating the first solution",
            ],
            "answer_index": 0,
        },
        "learning_meta": {
            "elaboration": "Inversion exposes hidden assumptions and makes risks concrete before they become expensive.",
            "real_world_example": "Before launching a study plan, ask: what would make me quit after one week?",
            "misconception_note": "Inversion is not pessimism; it is prevention.",
        },
    },
    {
        "id": 2,
        "front": "What does circle of competence help you decide?",
        "back": "It helps you separate areas you understand well from areas where your confidence is not justified.",
        "difficulty": "medium",
        "card_type": "application",
        "source_ref": "mental models",
        "mcq_options": {
            "choices": [
                "Whether your judgment is likely reliable",
                "Whether a topic is fashionable",
                "Whether a choice feels exciting",
                "Whether experts always agree",
            ],
            "answer_index": 0,
        },
        "learning_meta": {
            "elaboration": "The model improves decisions by encouraging humility at the boundary of your knowledge.",
            "real_world_example": "You may understand a company product but not its regulatory risk.",
            "misconception_note": "The goal is not to stay small forever; it is to know when you are learning versus betting.",
        },
    },
    {
        "id": 3,
        "front": "How does first-principles thinking differ from reasoning by analogy?",
        "back": "First-principles thinking rebuilds from basic truths, while analogy copies patterns from similar situations.",
        "difficulty": "medium",
        "card_type": "contrast",
        "source_ref": "mental models",
        "mcq_options": {
            "choices": [
                "It rebuilds from fundamentals instead of copying a similar case",
                "It always uses historical precedent",
                "It avoids breaking a problem down",
                "It depends on popularity signals",
            ],
            "answer_index": 0,
        },
        "learning_meta": {
            "elaboration": "Analogy is fast, but first principles can reveal better options when old patterns constrain thinking.",
            "real_world_example": "Instead of asking how courses are usually taught, ask what memory needs to form.",
            "misconception_note": "First principles do not mean ignoring experience; they mean testing which parts are actually necessary.",
        },
    },
    {
        "id": 4,
        "front": "What is second-order thinking?",
        "back": "Second-order thinking asks what happens after the immediate effect of a decision.",
        "difficulty": "easy",
        "card_type": "why",
        "source_ref": "mental models",
        "mcq_options": {
            "choices": [
                "Considering consequences beyond the first outcome",
                "Picking the fastest visible fix",
                "Avoiding tradeoffs",
                "Doing two tasks at once",
            ],
            "answer_index": 0,
        },
        "learning_meta": {
            "elaboration": "Many bad decisions look good at first because their delayed costs are hidden.",
            "real_world_example": "Cramming may raise tomorrow's score but weaken long-term retention.",
            "misconception_note": "Second-order thinking is not overthinking every tiny choice; use it where consequences compound.",
        },
    },
    {
        "id": 5,
        "front": "What does opportunity cost mean?",
        "back": "Opportunity cost is the value of the best alternative you give up when making a choice.",
        "difficulty": "easy",
        "card_type": "recall",
        "source_ref": "mental models",
        "mcq_options": {
            "choices": [
                "The best forgone alternative",
                "The money already spent",
                "The cheapest visible option",
                "The effort saved by delaying",
            ],
            "answer_index": 0,
        },
        "learning_meta": {
            "elaboration": "It forces comparison against the best use of scarce time, attention, or money.",
            "real_world_example": "One hour scrolling is also one hour not practicing, resting, or building.",
            "misconception_note": "Opportunity cost includes non-money resources like focus and reputation.",
        },
    },
    {
        "id": 6,
        "front": "What is a feedback loop?",
        "back": "A feedback loop is a cycle where outputs of a system influence future behavior of that system.",
        "difficulty": "medium",
        "card_type": "recall",
        "source_ref": "mental models",
        "mcq_options": {
            "choices": [
                "A cycle where outcomes influence future inputs",
                "A one-time instruction",
                "A random event with no memory",
                "A list of unrelated actions",
            ],
            "answer_index": 0,
        },
        "learning_meta": {
            "elaboration": "Feedback loops explain momentum, habit formation, market reactions, and learning progress.",
            "real_world_example": "Small wins increase motivation, which increases practice, which creates more wins.",
            "misconception_note": "Not all feedback is useful; delayed or noisy feedback can mislead.",
        },
    },
]


def demo_deck_out() -> dict:
    return {**DEMO_DECK, "card_count": len(DEMO_CARDS)}
