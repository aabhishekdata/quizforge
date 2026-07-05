from datetime import datetime
from pydantic import BaseModel, Field


# ---------- auth ----------
class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)
    invite_code: str


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetIn(BaseModel):
    username: str
    reset_code: str
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetCreateIn(BaseModel):
    username: str


class PasswordResetCodeOut(BaseModel):
    code: str
    username: str
    created_at: datetime
    used_at: datetime | None = None


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    total_xp: int = 0
    level: int = 1
    level_progress: float = 0.0
    streak_current: int = 0
    freeze_tokens: int = 0

    class Config:
        from_attributes = True


# ---------- decks & cards ----------
class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = ""


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = None


class SubjectOut(BaseModel):
    id: int
    name: str
    description: str = ""
    deck_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class DeckCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    subject_id: int | None = None
    subject_name: str | None = Field(default=None, max_length=80)


class DeckUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    smart_review: bool | None = None
    subject_id: int | None = None
    subject_name: str | None = Field(default=None, max_length=80)


class CardOut(BaseModel):
    id: int
    front: str
    back: str
    mcq_options: dict | None = None
    difficulty: str
    card_type: str = "recall"
    learning_meta: dict | None = None
    source_ref: str | None = None

    class Config:
        from_attributes = True


class CardCreate(BaseModel):
    front: str = Field(min_length=1, max_length=1000)
    back: str = Field(min_length=1, max_length=2000)
    difficulty: str = "medium"


class CardUpdate(BaseModel):
    front: str | None = None
    back: str | None = None
    difficulty: str | None = None


class DeckOut(BaseModel):
    id: int
    title: str
    description: str
    owner_id: int
    owner_username: str = ""
    is_shared_with_me: bool = False
    subject_id: int | None = None
    subject_name: str | None = None
    smart_review: bool
    card_count: int = 0
    due_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ShareIn(BaseModel):
    username: str


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class GroupMemberIn(BaseModel):
    username: str


class GroupShareIn(BaseModel):
    group_id: int


class GroupOut(BaseModel):
    id: int
    name: str
    members: list[str] = []
    created_at: datetime


# ---------- study ----------
class ReviewIn(BaseModel):
    card_id: int
    mode: str  # flashcard | mcq | type | match
    rating: int  # 1..4
    correct: bool
    ms_taken: int | None = None
    combo: int = 0  # current in-session correct streak (client-tracked, server-capped)


class ReviewOut(BaseModel):
    xp_awarded: int
    total_xp: int
    level: int
    level_progress: float
    new_achievements: list[dict] = []
    next_due: datetime | None = None


class SessionCompleteIn(BaseModel):
    deck_id: int
    cards_seen: int
    correct: int


# ---------- documents ----------
class DocumentOut(BaseModel):
    id: int
    filename: str
    filetype: str
    status: str
    progress: str
    error: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- gamification ----------
class LeaderboardRow(BaseModel):
    username: str
    weekly_xp: int
    total_xp: int
    level: int
    streak: int


class AchievementOut(BaseModel):
    key: str
    name: str
    description: str
    icon: str
    earned_at: datetime | None = None


class ProfileDeckStat(BaseModel):
    deck_id: int
    title: str
    subject_name: str | None = None
    reviews: int
    correct: int
    last_studied_at: datetime | None = None


class ProfileStatsOut(BaseModel):
    username: str
    is_admin: bool
    total_xp: int
    weekly_xp: int
    level: int
    level_progress: float
    streak_current: int
    streak_longest: int
    freeze_tokens: int
    decks_owned: int
    decks_shared_with_me: int
    subjects: int
    cards_owned: int
    decks_studied: int
    reviews: int
    correct_reviews: int
    accuracy: float
    study_sessions_completed: int
    achievements_earned: int
    recent_decks: list[ProfileDeckStat] = []
