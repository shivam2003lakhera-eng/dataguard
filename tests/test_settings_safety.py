from app.core.config import Settings


def test_settings_repr_does_not_reveal_database_passwords():
    settings = Settings(
        database_url="postgresql+psycopg://u:SECRETPW1@localhost/db",
        test_database_url="postgresql+psycopg://u:SECRETPW2@localhost/db_test",
        _env_file=None,
    )
    shown = repr(settings) + str(settings)
    assert "SECRETPW1" not in shown and "SECRETPW2" not in shown
    assert "max_file_size_mb" in shown  # still useful for debugging