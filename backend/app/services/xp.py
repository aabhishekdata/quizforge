"""Gamification engine: XP ledger, level curve, streaks, achievements."""
from datetime import datetime, date, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models

# ---------- XP rules ----------
XP_CORRECT = 5
XP_INCORRECT = 2          # effort still counts
XP_DECK_COMPLETE = 50
XP_DAILY_FIRST = 20
COMBO_THRESHOLD = 5       # 5+ correct in a row -> multiplier
COMBO_MULTIPLIER = 1.5
MATCH_SPEED_BONUS_MAX = 30

LEVEL_TITLES = [
    (1, "Novice"), (5, "Apprentice"), (10, "Scholar"),
    (15, "Adept"), (20, "Sage"), (30, "Grandmaster"),
]


def xp_for_level(level: int) -> int:
    """Cumulative XP required to *reach* this level."""
    return sum(int(100 * (n ** 1.5)) for n in range(1, level))


def level_from_xp(total_xp: int) -> tuple[int, float]:
    """Return (level, progress 0..1 toward next level)."""
    level = 1
    while xp_for_level(level + 1) <= total_xp:
        level += 1
    floor = xp_for_level(level)
    ceil = xp_for_level(level + 1)
    progress = (total_xp - floor) / max(1, ceil - floor)
    return level, round(progress, 4)


def title_for_level(level: int) -> str:
    title = LEVEL_TITLES[0][1]
    for lv, t in LEVEL_TITLES:
        if level >= lv:
            title = t
    return title


def total_xp(db: Session, user_id: int) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(models.XPEvent.amount), 0))
        .where(models.XPEvent.user_id == user_id)
    ) or 0


def weekly_xp(db: Session, user_id: int) -> int:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    start = datetime.combine(monday, datetime.min.time())
    return db.scalar(
        select(func.coalesce(func.sum(models.XPEvent.amount), 0))
        .where(models.XPEvent.user_id == user_id,
               models.XPEvent.created_at >= start)
    ) or 0


def award(db: Session, user_id: int, amount: int, reason: str, meta: dict | None = None) -> int:
    if amount <= 0:
        return 0
    db.add(models.XPEvent(user_id=user_id, amount=amount, reason=reason, meta=meta))
    return amount


def review_xp(correct: bool, combo: int, mode: str, ms_taken: int | None) -> int:
    base = XP_CORRECT if correct else XP_INCORRECT
    if correct and combo >= COMBO_THRESHOLD:
        base = int(base * COMBO_MULTIPLIER)
    if mode == "match" and correct and ms_taken is not None:
        # faster matches earn up to MATCH_SPEED_BONUS_MAX extra
        bonus = max(0, MATCH_SPEED_BONUS_MAX - ms_taken // 1000)
        base += min(bonus, MATCH_SPEED_BONUS_MAX)
    return base


# ---------- streaks ----------
def get_or_create_streak(db: Session, user_id: int) -> models.Streak:
    s = db.scalar(select(models.Streak).where(models.Streak.user_id == user_id))
    if not s:
        s = models.Streak(user_id=user_id)
        db.add(s)
        db.flush()
    return s


def touch_streak(db: Session, user_id: int) -> tuple[models.Streak, bool]:
    """Called on any completed review. Returns (streak, is_first_study_today)."""
    s = get_or_create_streak(db, user_id)
    today = date.today()
    if s.last_study_date == today:
        return s, False
    if s.last_study_date == today - timedelta(days=1):
        s.current += 1
    elif s.last_study_date is not None and s.last_study_date == today - timedelta(days=2) and s.freeze_tokens > 0:
        # one missed day, auto-consume a freeze token
        s.freeze_tokens -= 1
        s.current += 1
    else:
        s.current = 1
    s.longest = max(s.longest, s.current)
    s.last_study_date = today
    return s, True


# ---------- achievements ----------
SEED_ACHIEVEMENTS = [
    ("first_deck", "First Deck", "Create or generate your first deck", "📚", 25),
    ("first_hundred", "Century", "Review 100 cards total", "💯", 50),
    ("perfectionist", "Perfectionist", "Finish a 20+ card session with 100% correct", "🎯", 75),
    ("streak_7", "One Week Wonder", "Reach a 7-day streak", "🔥", 50),
    ("streak_30", "Monthly Devotion", "Reach a 30-day streak", "🌋", 200),
    ("night_owl", "Night Owl", "Study between midnight and 4am", "🦉", 25),
    ("early_bird", "Early Bird", "Study before 7am", "🐦", 25),
    ("comeback", "Comeback", "Return after 7+ days away", "🎭", 25),
    ("level_5", "Apprentice", "Reach level 5", "⭐", 50),
    ("level_10", "Scholar", "Reach level 10", "🌟", 100),
    ("match_master", "Match Master", "Complete 10 match-mode sessions", "🧩", 50),
    ("uploader", "Feed the Machine", "Upload 5 documents", "📄", 40),
    ("sharer", "Study Buddy", "Share a deck with a friend", "🤝", 25),
    ("smart_start", "Galaxy Brain", "Enable Smart Review on a deck", "🧠", 25),
    ("thousand_club", "Thousand Club", "Earn 1,000 total XP", "🏆", 100),
]


def seed_achievements(db: Session):
    existing = {a.key for a in db.scalars(select(models.Achievement)).all()}
    for key, name, desc, icon, xp in SEED_ACHIEVEMENTS:
        if key not in existing:
            db.add(models.Achievement(key=key, name=name, description=desc, icon=icon, xp_reward=xp))
    db.commit()


def grant(db: Session, user_id: int, key: str) -> dict | None:
    ach = db.scalar(select(models.Achievement).where(models.Achievement.key == key))
    if not ach:
        return None
    already = db.scalar(select(models.UserAchievement).where(
        models.UserAchievement.user_id == user_id,
        models.UserAchievement.achievement_id == ach.id))
    if already:
        return None
    db.add(models.UserAchievement(user_id=user_id, achievement_id=ach.id))
    award(db, user_id, ach.xp_reward, f"achievement:{key}")
    return {"key": ach.key, "name": ach.name, "icon": ach.icon, "xp": ach.xp_reward}


def check_review_achievements(db: Session, user_id: int) -> list[dict]:
    """Cheap checks run after each review. Returns newly earned achievements."""
    earned = []
    now = datetime.utcnow()
    hour = now.hour
    if 0 <= hour < 4:
        r = grant(db, user_id, "night_owl")
        if r: earned.append(r)
    if 4 <= hour < 7:
        r = grant(db, user_id, "early_bird")
        if r: earned.append(r)

    total_reviews = db.scalar(
        select(func.count(models.ReviewLog.id)).where(models.ReviewLog.user_id == user_id)) or 0
    if total_reviews >= 100:
        r = grant(db, user_id, "first_hundred")
        if r: earned.append(r)

    txp = total_xp(db, user_id)
    if txp >= 1000:
        r = grant(db, user_id, "thousand_club")
        if r: earned.append(r)
    level, _ = level_from_xp(txp)
    if level >= 5:
        r = grant(db, user_id, "level_5")
        if r: earned.append(r)
    if level >= 10:
        r = grant(db, user_id, "level_10")
        if r: earned.append(r)

    s = db.scalar(select(models.Streak).where(models.Streak.user_id == user_id))
    if s:
        if s.current >= 7:
            r = grant(db, user_id, "streak_7")
            if r: earned.append(r)
        if s.current >= 30:
            r = grant(db, user_id, "streak_30")
            if r: earned.append(r)
    return earned
