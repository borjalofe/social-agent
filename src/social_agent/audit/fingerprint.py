"""Finding fingerprints for issue dedupe."""

from __future__ import annotations

import hashlib
import re

_WS = re.compile(r"\s+")


def normalize_message(message: str) -> str:
    return _WS.sub(" ", message.strip()).lower()


def fingerprint(rule_id: str, path: str, message: str) -> str:
    """Stable id from rule/id + path + normalized message (vault MECE contract)."""
    payload = f"{rule_id}\n{path}\n{normalize_message(message)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
