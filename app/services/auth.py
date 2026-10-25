from datetime import UTC, datetime, timedelta
from functools import lru_cache

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, InvalidCredentialsError, RegistrationClosedError
from app.core.security import generate_token, hash_password, hash_token, verify_password
from app.models import User, UserSession

SESSION_COOKIE = "dataguard_session"


@lru_cache
def _dummy_hash() -> str:
    """Checked when the email is unknown, so timing doesn't reveal which emails exist."""
    return hash_password("dummy-password-for-timing")


def register_user(db: Session, email: str, password: str) -> User:
    if not get_settings().allow_registration:
        raise RegistrationClosedError("Registration is closed.")
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise ConflictError("An account with this email already exists.")

    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two requests registered the same email at once
        db.rollback()
        raise ConflictError("An account with this email already exists.") from None
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    stored = user.password_hash if user else _dummy_hash()
    password_ok = verify_password(password, stored)
    if user is None or not password_ok:
        raise InvalidCredentialsError("Incorrect email or password.")
    return user


def start_session(db: Session, user: User) -> str:
    """Create a login and return the token for the cookie. Only its hash is stored."""
    now = datetime.now(UTC)
    token = generate_token()
    db.execute(
        delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at < now)
    )
    db.add(UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(days=get_settings().session_days),
    ))
    db.commit()
    return token


def user_for_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == hash_token(token),
            UserSession.expires_at > datetime.now(UTC),
        )
    )
    return session.user if session else None


def end_session(db: Session, token: str) -> None:
    db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
    db.commit()