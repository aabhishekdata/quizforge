import enum
from datetime import datetime, date
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Date, Text, ForeignKey,
    Enum, UniqueConstraint, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utcnow():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    decks = relationship("Deck", back_populates="owner")
    xp_events = relationship("XPEvent", back_populates="user")
    streak = relationship("Streak", back_populates="user", uselist=False)


class InviteCode(Base):
    __tablename__ = "invite_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    used_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DocStatus(str, enum.Enum):
    pending = "pending"
    parsing = "parsing"
    generating = "generating"
    ready = "ready"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    filetype: Mapped[str] = mapped_column(String(10))  # pdf|docx|pptx|epub|md
    stored_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[DocStatus] = mapped_column(Enum(DocStatus), default=DocStatus.pending)
    progress: Mapped[str] = mapped_column(String(255), default="Queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Deck(Base):
    __tablename__ = "decks"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)  # private by default
    smart_review: Mapped[bool] = mapped_column(Boolean, default=False)  # FSRS opt-in
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    owner = relationship("User", back_populates="decks")
    cards = relationship("Card", back_populates="deck", cascade="all, delete-orphan")


class DeckShare(Base):
    """Per-deck sharing with specific users."""
    __tablename__ = "deck_shares"
    id: Mapped[int] = mapped_column(primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("deck_id", "user_id"),)


class StudyGroup(Base):
    __tablename__ = "study_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StudyGroupMember(Base):
    __tablename__ = "study_group_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("study_groups.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("group_id", "user_id"),)


class DeckGroupShare(Base):
    __tablename__ = "deck_group_shares"
    id: Mapped[int] = mapped_column(primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("study_groups.id"))
    shared_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    shared_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("deck_id", "group_id"),)


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[int] = mapped_column(primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id"))
    front: Mapped[str] = mapped_column(Text)          # term / question
    back: Mapped[str] = mapped_column(Text)           # definition / answer
    mcq_options: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"choices": [...], "answer_index": 0}
    difficulty: Mapped[str] = mapped_column(String(10), default="medium")  # easy|medium|hard
    card_type: Mapped[str] = mapped_column(String(20), default="recall")  # recall|why|application|contrast|derivation
    learning_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g. "page 12"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    deck = relationship("Deck", back_populates="cards")


class CardReview(Base):
    """FSRS scheduling state per (user, card) + append-only history via ReviewLog."""
    __tablename__ = "card_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    stability: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty: Mapped[float] = mapped_column(Float, default=5.0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_review: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "card_id"),)


class ReviewLog(Base):
    __tablename__ = "review_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    mode: Mapped[str] = mapped_column(String(20))  # flashcard|mcq|type|match
    rating: Mapped[int] = mapped_column(Integer)   # 1 again, 2 hard, 3 good, 4 easy (mcq/type: 1 wrong, 3 right)
    correct: Mapped[bool] = mapped_column(Boolean)
    ms_taken: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class XPEvent(Base):
    """Append-only XP ledger. Leaderboards/levels are sums over this table."""
    __tablename__ = "xp_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(50))  # review_correct, deck_complete, daily_first, combo_bonus...
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    user = relationship("User", back_populates="xp_events")


class Streak(Base):
    __tablename__ = "streaks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    current: Mapped[int] = mapped_column(Integer, default=0)
    longest: Mapped[int] = mapped_column(Integer, default=0)
    last_study_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    freeze_tokens: Mapped[int] = mapped_column(Integer, default=2)

    user = relationship("User", back_populates="streak")


class Achievement(Base):
    __tablename__ = "achievements"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    icon: Mapped[str] = mapped_column(String(10), default="🏅")
    xp_reward: Mapped[int] = mapped_column(Integer, default=25)


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id"))
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "achievement_id"),)
