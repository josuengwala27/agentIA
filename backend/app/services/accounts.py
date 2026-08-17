"""Helpers for admin account management."""

from __future__ import annotations

import secrets
import string

from app.models import UserRole

ALLOWED_ROLES = {
    UserRole.LEARNER.value,
    UserRole.TRAINER.value,
    UserRole.ADMIN.value,
}


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_role(role: str) -> str:
    value = (role or "").strip().lower()
    if value not in ALLOWED_ROLES:
        raise ValueError("Rôle invalide")
    return value


def generate_temporary_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(max(8, length)))
