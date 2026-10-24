from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.models import User, UserSession


def make_user(email="a@example.com") -> User:
    return User(email=email, password_hash="not-a-real-hash")


def make_session(user, token_hash="h" * 64) -> UserSession:
    return UserSession(
        user=user, token_hash=token_hash, expires_at=datetime.now(UTC) + timedelta(days=1)
    )


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def assert_rejected(session, *objects):
    session.add_all(objects)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_user_and_session_round_trip(db_session):
    user = make_user()
    db_session.add_all([user, make_session(user)])
    db_session.commit()
    db_session.expire_all()

    loaded = db_session.scalars(select(User)).one()
    assert loaded.created_at is not None
    assert loaded.sessions[0].token_hash == "h" * 64


def test_duplicate_email_is_rejected(db_session):
    assert_rejected(db_session, make_user("same@example.com"), make_user("same@example.com"))


def test_uppercase_email_is_rejected_by_the_database(db_session):
    assert_rejected(db_session, make_user("Upper@Example.com"))


def test_duplicate_token_hash_is_rejected(db_session):
    first, second = make_user("one@example.com"), make_user("two@example.com")
    assert_rejected(db_session, first, second, make_session(first), make_session(second))


def test_deleting_a_user_through_the_orm_removes_sessions(db_session):
    user = make_user()
    db_session.add_all([user, make_session(user)])
    db_session.commit()

    db_session.delete(user)
    db_session.commit()
    assert count(db_session, UserSession) == 0


def test_database_level_cascade_works_without_the_orm(db_session):
    user = make_user()
    db_session.add_all([user, make_session(user)])
    db_session.commit()

    db_session.execute(delete(User))
    db_session.commit()
    assert count(db_session, UserSession) == 0