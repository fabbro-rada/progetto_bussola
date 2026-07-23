"""Password hashing (argon2id). Passwords are never logged or stored in clear."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()
# A fixed hash used only to spend comparable CPU time when the username is
# unknown, so login timing does not reveal whether an account exists.
_DUMMY_HASH = _hasher.hash("timing-equalization-placeholder")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(hash_: str, password: str) -> bool:
    try:
        return _hasher.verify(hash_, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def dummy_verify() -> None:
    """Verify against a fixed hash to equalize timing for unknown users."""
    try:
        _hasher.verify(_DUMMY_HASH, "wrong")
    except VerifyMismatchError:
        pass
