import base64
import hashlib
import hmac
import os
from typing import Tuple

from cryptography.fernet import Fernet


def generate_salt() -> str:
    return base64.urlsafe_b64encode(os.urandom(16)).decode("utf-8")


def _salt_bytes(salt: str) -> bytes:
    return base64.urlsafe_b64decode(salt.encode("utf-8"))


def hash_pin(pin: str, salt: str) -> str:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        _salt_bytes(salt),
        200_000,
    )
    return base64.urlsafe_b64encode(derived).decode("utf-8")


def verify_pin(pin: str, salt: str, expected_hash: str) -> bool:
    current = hash_pin(pin, salt)
    return hmac.compare_digest(current, expected_hash)


def build_fernet(pin: str, salt: str, pepper: str) -> Fernet:
    key_material = hashlib.pbkdf2_hmac(
        "sha256",
        f"{pin}{pepper}".encode("utf-8"),
        _salt_bytes(salt),
        250_000,
        dklen=32,
    )
    key = base64.urlsafe_b64encode(key_material)
    return Fernet(key)


def generate_share_key() -> Tuple[str, Fernet]:
    key = Fernet.generate_key()
    return key.decode("utf-8"), Fernet(key)
