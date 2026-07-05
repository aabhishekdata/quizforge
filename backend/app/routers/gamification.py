import secrets
import string

from fastapi import APIRouter, Depends
from fastapi import HTTPException
from sqlalchemy import select, func, distinct, or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import current_user, admin_user
from ..services import xp

router = APIRouter(prefix="/api", tags=["gamification"])


@router.get("/leaderboard", response_model=list[schemas.LeaderboardRow])
def leaderboard(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    rows = []
    for u in db.scalars(select(models.User)).all():
        txp = xp.total_xp(db, u.id)
        level, _ = xp.level_from_xp(txp)
        streak = db.scalar(select(models.Streak).where(models.Streak.user_id == u.id))
        rows.append(schemas.LeaderboardRow(
            username=u.username, weekly_xp=xp.weekly_xp(db, u.id),
            total_xp=txp, level=level, streak=streak.current if streak else 0))
    rows.sort(key=lambda r: r.weekly_xp, reverse=True)
    return rows


@router.get("/achievements", response_model=list[schemas.AchievementOut])
def achievements(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    earned = {ua.achievement_id: ua.earned_at for ua in db.scalars(
        select(models.UserAchievement).where(models.UserAchievement.user_id == user.id)).all()}
    out = []
    for a in db.scalars(select(models.Achievement)).all():
        out.append(schemas.AchievementOut(
            key=a.key, name=a.name, description=a.description,
            icon=a.icon, earned_at=earned.get(a.id)))
    out.sort(key=lambda a: (a.earned_at is None, a.key))
    return out


@router.get("/profile", response_model=schemas.ProfileStatsOut)
def profile(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    shared_ids = select(models.DeckShare.deck_id).where(models.DeckShare.user_id == user.id)
    group_shared_ids = (
        select(models.DeckGroupShare.deck_id)
        .join(models.StudyGroupMember, models.StudyGroupMember.group_id == models.DeckGroupShare.group_id)
        .where(models.StudyGroupMember.user_id == user.id)
    )
    accessible_deck_filter = or_(
        models.Deck.owner_id == user.id,
        models.Deck.id.in_(shared_ids),
        models.Deck.id.in_(group_shared_ids),
    )

    txp = xp.total_xp(db, user.id)
    level, progress = xp.level_from_xp(txp)
    streak = db.scalar(select(models.Streak).where(models.Streak.user_id == user.id))

    decks_owned = db.scalar(select(func.count(models.Deck.id)).where(models.Deck.owner_id == user.id)) or 0
    subjects = db.scalar(select(func.count(models.Subject.id)).where(models.Subject.owner_id == user.id)) or 0
    cards_owned = db.scalar(
        select(func.count(models.Card.id))
        .join(models.Deck, models.Deck.id == models.Card.deck_id)
        .where(models.Deck.owner_id == user.id)
    ) or 0
    shared_direct = db.scalar(select(func.count(models.DeckShare.id)).where(models.DeckShare.user_id == user.id)) or 0
    shared_group = db.scalar(
        select(func.count(distinct(models.DeckGroupShare.deck_id)))
        .join(models.StudyGroupMember, models.StudyGroupMember.group_id == models.DeckGroupShare.group_id)
        .where(models.StudyGroupMember.user_id == user.id)
    ) or 0

    review_rows = (
        select(
            func.count(models.ReviewLog.id),
            func.coalesce(func.sum(models.ReviewLog.correct.cast(models.Integer)), 0),
            func.count(distinct(models.Card.deck_id)),
        )
        .join(models.Card, models.Card.id == models.ReviewLog.card_id)
        .join(models.Deck, models.Deck.id == models.Card.deck_id)
        .where(models.ReviewLog.user_id == user.id, accessible_deck_filter)
    )
    reviews, correct_reviews, decks_studied = db.execute(review_rows).one()
    reviews = reviews or 0
    correct_reviews = correct_reviews or 0
    decks_studied = decks_studied or 0

    recent_rows = db.execute(
        select(
            models.Deck.id,
            models.Deck.title,
            models.Subject.name,
            func.count(models.ReviewLog.id).label("reviews"),
            func.coalesce(func.sum(models.ReviewLog.correct.cast(models.Integer)), 0).label("correct"),
            func.max(models.ReviewLog.created_at).label("last_studied_at"),
        )
        .join(models.Card, models.Card.deck_id == models.Deck.id)
        .join(models.ReviewLog, models.ReviewLog.card_id == models.Card.id)
        .outerjoin(models.Subject, models.Subject.id == models.Deck.subject_id)
        .where(models.ReviewLog.user_id == user.id, accessible_deck_filter)
        .group_by(models.Deck.id, models.Deck.title, models.Subject.name)
        .order_by(func.max(models.ReviewLog.created_at).desc())
        .limit(5)
    ).all()

    recent_decks = [
        schemas.ProfileDeckStat(
            deck_id=row.id,
            title=row.title,
            subject_name=row.name,
            reviews=row.reviews,
            correct=row.correct,
            last_studied_at=row.last_studied_at,
        )
        for row in recent_rows
    ]

    completed = db.scalar(
        select(func.count(models.XPEvent.id)).where(
            models.XPEvent.user_id == user.id,
            models.XPEvent.reason == "deck_complete",
        )
    ) or 0
    achievements_earned = db.scalar(
        select(func.count(models.UserAchievement.id)).where(models.UserAchievement.user_id == user.id)
    ) or 0

    return schemas.ProfileStatsOut(
        username=user.username,
        is_admin=user.is_admin,
        total_xp=txp,
        weekly_xp=xp.weekly_xp(db, user.id),
        level=level,
        level_progress=progress,
        streak_current=streak.current if streak else 0,
        streak_longest=streak.longest if streak else 0,
        freeze_tokens=streak.freeze_tokens if streak else 2,
        decks_owned=decks_owned,
        decks_shared_with_me=shared_direct + shared_group,
        subjects=subjects,
        cards_owned=cards_owned,
        decks_studied=decks_studied,
        reviews=reviews,
        correct_reviews=correct_reviews,
        accuracy=round((correct_reviews / reviews) * 100, 1) if reviews else 0.0,
        study_sessions_completed=completed,
        achievements_earned=achievements_earned,
        recent_decks=recent_decks,
    )


# ---------- admin: invite codes ----------
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


def _new_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


@admin_router.post("/invites")
def create_invite(admin: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    code = models.InviteCode(code=_new_code(), created_by=admin.id)
    db.add(code)
    db.commit()
    return {"code": code.code}


@admin_router.get("/invites")
def list_invites(admin: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    codes = db.scalars(select(models.InviteCode).order_by(models.InviteCode.created_at.desc())).all()
    out = []
    for c in codes:
        used_by = db.get(models.User, c.used_by).username if c.used_by else None
        out.append({"code": c.code, "used_by": used_by, "created_at": c.created_at})
    return out


@admin_router.post("/password-resets", response_model=schemas.PasswordResetCodeOut)
def create_password_reset(
    body: schemas.PasswordResetCreateIn,
    admin: models.User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    target = db.scalar(select(models.User).where(models.User.username == body.username.strip()))
    if not target:
        raise HTTPException(404, f"No user named {body.username}")
    code = models.PasswordResetCode(code=_new_code(), user_id=target.id, created_by=admin.id)
    db.add(code)
    db.commit()
    return schemas.PasswordResetCodeOut(
        code=code.code,
        username=target.username,
        created_at=code.created_at,
        used_at=code.used_at,
    )


@admin_router.get("/password-resets", response_model=list[schemas.PasswordResetCodeOut])
def list_password_resets(admin: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(models.PasswordResetCode).order_by(models.PasswordResetCode.created_at.desc()).limit(25)).all()
    out = []
    for row in rows:
        target = db.get(models.User, row.user_id)
        out.append(schemas.PasswordResetCodeOut(
            code=row.code,
            username=target.username if target else "unknown",
            created_at=row.created_at,
            used_at=row.used_at,
        ))
    return out


def _group_out(db: Session, group: models.StudyGroup) -> schemas.GroupOut:
    members = db.scalars(
        select(models.User.username)
        .join(models.StudyGroupMember, models.StudyGroupMember.user_id == models.User.id)
        .where(models.StudyGroupMember.group_id == group.id)
        .order_by(models.User.username)
    ).all()
    return schemas.GroupOut(
        id=group.id,
        name=group.name,
        members=list(members),
        created_at=group.created_at,
    )


@admin_router.get("/groups", response_model=list[schemas.GroupOut])
def list_groups(admin: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    groups = db.scalars(select(models.StudyGroup).order_by(models.StudyGroup.name)).all()
    return [_group_out(db, g) for g in groups]


@admin_router.post("/groups", response_model=schemas.GroupOut)
def create_group(body: schemas.GroupCreate, admin: models.User = Depends(admin_user),
                 db: Session = Depends(get_db)):
    name = body.name.strip()
    if db.scalar(select(models.StudyGroup).where(models.StudyGroup.name == name)):
        raise HTTPException(400, "A group with that name already exists")
    group = models.StudyGroup(name=name, created_by=admin.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    return _group_out(db, group)


@admin_router.post("/groups/{group_id}/members", response_model=schemas.GroupOut)
def add_group_member(group_id: int, body: schemas.GroupMemberIn,
                     admin: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    group = db.get(models.StudyGroup, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    user = db.scalar(select(models.User).where(models.User.username == body.username.strip()))
    if not user:
        raise HTTPException(404, f"No user named {body.username}")
    exists = db.scalar(select(models.StudyGroupMember).where(
        models.StudyGroupMember.group_id == group.id,
        models.StudyGroupMember.user_id == user.id,
    ))
    if not exists:
        db.add(models.StudyGroupMember(group_id=group.id, user_id=user.id))
        db.commit()
    return _group_out(db, group)


@admin_router.delete("/groups/{group_id}/members/{username}", response_model=schemas.GroupOut)
def remove_group_member(group_id: int, username: str,
                        admin: models.User = Depends(admin_user), db: Session = Depends(get_db)):
    group = db.get(models.StudyGroup, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    user = db.scalar(select(models.User).where(models.User.username == username))
    if user:
        db.query(models.StudyGroupMember).filter_by(group_id=group.id, user_id=user.id).delete()
        db.commit()
    return _group_out(db, group)
