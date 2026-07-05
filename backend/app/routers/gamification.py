import secrets
import string

from fastapi import APIRouter, Depends
from fastapi import HTTPException
from sqlalchemy import select
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
