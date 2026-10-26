"""Fernet seal/unseal helpers for LLM (and later) secrets."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from social_agent.crypto.fernet_box import (
    FernetBoxError,
    generate_key,
    seal,
    unseal,
)


def test_seal_unseal_roundtrip() -> None:
    key = generate_key()
    token = seal("sk-secret-value", key=key)
    assert token != "sk-secret-value"
    assert unseal(token, key=key) == "sk-secret-value"


def test_unseal_with_wrong_key_fails() -> None:
    token = seal("payload", key=generate_key())
    with pytest.raises(FernetBoxError):
        unseal(token, key=generate_key())


def test_seal_requires_key_or_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FERNET_KEY", raising=False)
    with pytest.raises(FernetBoxError, match="FERNET_KEY"):
        seal("x")


def test_seal_uses_fernet_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("FERNET_KEY", key)
    token = seal("from-env")
    assert unseal(token) == "from-env"


def test_generate_key_is_url_safe_fernet_key() -> None:
    key = generate_key()
    # Must be accepted by Fernet constructor.
    assert Fernet(key).encrypt(b"ok")
