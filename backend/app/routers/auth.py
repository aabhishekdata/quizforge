from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import hash_password, verify_password, set_session, clear_session, current_user
from ..services import xp

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(db: Session, user: models.User) -> schemas.UserOut:
    txp = xp.total_xp(db, user.id)
    level, progress = xp.level_from_xp(txp)
    streak = db.scalar(select(models.Streak).where(models.Streak.user_id == user.id))
    return schemas.UserOut(
        id=user.id, username=user.username, is_admin=user.is_admin,
        total_xp=txp, level=level, level_progress=progress,
        streak_current=streak.current if streak else 0,
        freeze_tokens=streak.freeze_tokens if streak else 2,
    )


@router.post("/register", response_model=schemas.UserOut)
def register(body: schemas.RegisterIn, response: Response, db: Session = Depends(get_db)):
    invite = db.scalar(select(models.InviteCode).where(
        models.InviteCode.code == body.invite_code.strip().upper(),
        models.InviteCode.used_by.is_(None)))
    if not invite:
        raise HTTPException(400, "Invite code is invalid or already used")
    if db.scalar(select(models.User).where(models.User.username == body.username)):
        raise HTTPException(400, "That username is taken")

    is_first_user = db.query(models.User).count() == 0
    user = models.User(
        username=body.username,
        password_hash=hash_password(body.password),
        is_admin=is_first_user,  # first account becomes admin
    )
    db.add(user)
    db.flush()
    invite.used_by = user.id
    invite.used_at = datetime.utcnow()
    db.add(models.Streak(user_id=user.id))
    db.commit()
    set_session(response, user.id)
    return _user_out(db, user)


@router.post("/login", response_model=schemas.UserOut)
def login(body: schemas.LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.username == body.username))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong username or password")
    set_session(response, user.id)
    return _user_out(db, user)


@router.post("/logout")
def logout(response: Response):
    clear_session(response)
    return {"ok": True}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    return _user_out(db, user)


@router.post("/password/change")
def change_password(
    body: schemas.PasswordChangeIn,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


@router.post("/password/reset", response_model=schemas.UserOut)
def reset_password(body: schemas.PasswordResetIn, response: Response, db: Session = Depends(get_db)):
    target = db.scalar(select(models.User).where(models.User.username == body.username.strip()))
    if not target:
        raise HTTPException(400, "Reset code is invalid or expired")

    cutoff = datetime.utcnow() - timedelta(hours=24)
    code = db.scalar(select(models.PasswordResetCode).where(
        models.PasswordResetCode.user_id == target.id,
        models.PasswordResetCode.code == body.reset_code.strip().upper(),
        models.PasswordResetCode.used_at.is_(None),
        models.PasswordResetCode.created_at >= cutoff,
    ))
    if not code:
        raise HTTPException(400, "Reset code is invalid or expired")

    target.password_hash = hash_password(body.new_password)
    code.used_at = datetime.utcnow()
    db.commit()
    set_session(response, target.id)
    return _user_out(db, target)
