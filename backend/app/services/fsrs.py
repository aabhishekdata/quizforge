"""Simplified FSRS-style scheduler.

This is a compact approximation of FSRS: stability grows with successful
reviews (scaled by rating and item difficulty), lapses reset stability
partially. Good enough for a friend group; swap in the `fsrs` PyPI package
later for the full algorithm without changing the CardReview schema.
"""
from datetime import datetime, timedelta
from .. import models

MIN_STABILITY = 0.5      # days
MAX_INTERVAL = 365       # days
REQUEST_RETENTION = 0.9

# rating: 1 again, 2 hard, 3 good, 4 easy
RATING_STABILITY_FACTOR = {1: 0.4, 2: 1.1, 3: 2.2, 4: 3.5}
RATING_DIFFICULTY_DELTA = {1: +1.2, 2: +0.4, 3: -0.2, 4: -0.6}


def schedule(review: models.CardReview, rating: int, now: datetime | None = None) -> models.CardReview:
    now = now or datetime.utcnow()
    review.reps += 1
    review.difficulty = min(10.0, max(1.0, review.difficulty + RATING_DIFFICULTY_DELTA[rating]))

    if rating == 1:
        review.lapses += 1
        review.stability = max(MIN_STABILITY, review.stability * RATING_STABILITY_FACTOR[1])
    else:
        if review.stability <= 0:
            review.stability = {2: 1.0, 3: 2.5, 4: 5.0}[rating]
        else:
            difficulty_damp = (11 - review.difficulty) / 10  # harder items grow slower
            review.stability = min(
                MAX_INTERVAL,
                review.stability * RATING_STABILITY_FACTOR[rating] * (0.6 + difficulty_damp),
            )

    interval_days = max(MIN_STABILITY, review.stability * (REQUEST_RETENTION + 0.1))
    if rating == 1:
        review.due = now + timedelta(minutes=10)  # relearn same session
    else:
        review.due = now + timedelta(days=min(MAX_INTERVAL, interval_days))
    review.last_review = now
    return review
