from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from . import models

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
serializer = URLSafeTimedSerializer(settings.secret_key, salt="qf-session")


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    return pwd.verify(p, h)


def set_session(response: Response, user_id: int):
    token = serializer.dumps({"uid": user_id})
    response.set_cookie(
        settings.session_cookie,
        token,
        max_age=settings.session_max_age,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_session(response: Response):
    response.delete_cookie(settings.session_cookie, path="/")


def current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    token = request.cookies.get(settings.session_cookie)
    if not token:
        raise HTTPException(401, "Not signed in")
    try:
        data = serializer.loads(token, max_age=settings.session_max_age)
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Session expired — sign in again")
    user = db.get(models.User, data["uid"])
    if not user:
        raise HTTPException(401, "Account not found")
    return user


def admin_user(user: models.User = Depends(current_user)) -> models.User:
    if not user.is_admin:
        raise HTTPException(403, "Admin only")
    return user
