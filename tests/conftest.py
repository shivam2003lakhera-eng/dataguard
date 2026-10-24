import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

REQUIRED_TEST_DB = "dataguard_test"


@pytest.fixture(scope="session")
def test_engine():
    settings = get_settings()
    if not settings.test_database_url:
        pytest.exit("TEST_DATABASE_URL is not set in .env. Refusing to run DB tests.")

    test_url = make_url(settings.test_database_url)
    dev_url = make_url(settings.database_url)

    if test_url.database != REQUIRED_TEST_DB:
        pytest.exit(f"Test database must be named '{REQUIRED_TEST_DB}'. Refusing to continue.")
    if test_url.database == dev_url.database:
        pytest.exit("Test and development databases are the same. Refusing to continue.")

    engine = create_engine(test_url)
    with engine.connect() as conn:
        actual = conn.execute(text("select current_database()")).scalar()
    if actual != REQUIRED_TEST_DB:
        engine.dispose()
        pytest.exit(f"Connected to '{actual}', not '{REQUIRED_TEST_DB}'. Refusing to continue.")

    from app.db.base import Base
    import app.models  # noqa: F401  (registers the tables)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    session = sessionmaker(bind=test_engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        with test_engine.begin() as conn:
            conn.execute(text(
                "TRUNCATE quality_results, quality_runs, quality_rules, "
                                "dataset_profiles, datasets, user_sessions, users RESTART IDENTITY CASCADE"
            ))