import pytest

from app.services.accounts import generate_temporary_password, normalize_email, validate_role


def test_normalize_email() -> None:
    assert normalize_email("  Ada@Demo.Local ") == "ada@demo.local"


def test_validate_role_accepts_known_roles() -> None:
    assert validate_role("Learner") == "learner"
    assert validate_role("trainer") == "trainer"
    assert validate_role("admin") == "admin"


def test_validate_role_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        validate_role("superuser")


def test_temporary_password_is_long_enough() -> None:
    password = generate_temporary_password()
    assert len(password) >= 8
    assert password.isalnum()
