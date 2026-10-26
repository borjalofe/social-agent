"""Fernet seal/unseal for secrets stored in the database."""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class FernetBoxError(RuntimeError):
    """Raised when a Fernet key is missing or a token cannot be opened."""


def generate_key() -> bytes:
    """Return a new url-safe Fernet key (store only in env / secret manager)."""
    return Fernet.generate_key()


def _fernet(key: bytes | str | None = None) -> Fernet:
    if key is None:
        raw = os.environ.get("FERNET_KEY")
        if not raw:
            raise FernetBoxError("FERNET_KEY is required to seal/unseal secrets")
        key = raw
    if isinstance(key, str):
        key = key.encode("ascii")
    try:
        return Fernet(key)
    except (TypeError, ValueError) as exc:
        raise FernetBoxError("invalid Fernet key") from exc


def seal(plaintext: str, *, key: bytes | str | None = None) -> str:
    """Encrypt plaintext; return ascii Fernet token suitable for a Text column."""
    token = _fernet(key).encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def unseal(token: str, *, key: bytes | str | None = None) -> str:
    """Decrypt a Fernet token produced by `seal`."""
    try:
        return _fernet(key).decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise FernetBoxError("unable to unseal token with the given key") from exc
