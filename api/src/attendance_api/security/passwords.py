from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, candidate: str) -> bool:
    try:
        return _hasher.verify(password_hash, candidate)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_meets_policy(password: str) -> bool:
    return 12 <= len(password) <= 128
