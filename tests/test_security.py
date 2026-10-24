import pytest

from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    normalize_email,
    verify_password,
)


def test_correct_password_verifies():
    stored = hash_password("correct horse 9")
    assert verify_password("correct horse 9", stored) is True


def test_wrong_password_is_rejected():
    stored = hash_password("correct horse 9")
    assert verify_password("wrong horse 9", stored) is False


def test_stored_hash_does_not_contain_the_password():
    assert "correct horse" not in hash_password("correct horse 9")


def test_same_password_gets_different_hashes():
    assert hash_password("same-password-1") != hash_password("same-password-1")


def test_unicode_password_works():
    stored = hash_password("pässwörd✓-123")
    assert verify_password("pässwörd✓-123", stored) is True


@pytest.mark.parametrize(
    "stored",
    [
        "",
        "plain-text",
        "scrypt$1$2",
        "bcrypt$16384$8$1$AAAA$AAAA",
        "scrypt$abc$8$1$AAAA$AAAA",
        "scrypt$3$8$1$AAAA$AAAA",
    ],
)
def test_malformed_stored_hash_is_false_not_an_exception(stored):
    assert verify_password("anything", stored) is False


def test_generated_tokens_are_unique_and_long():
    first, second = generate_token(), generate_token()
    assert first != second
    assert len(first) >= 40


def test_token_hash_is_stable_hex_and_not_the_token():
    token = generate_token()
    digest = hash_token(token)
    assert digest == hash_token(token)
    assert digest != token
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_normalize_email():
    assert normalize_email("  Alice@Example.COM ") == "alice@example.com"