from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.security import verify_password


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if user and user.is_active and verify_password(password, user.password_hash):
        return user
    return None
