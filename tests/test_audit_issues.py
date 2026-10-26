"""Issue body marker and dedupe against open fingerprints."""

from __future__ import annotations

from social_agent.audit.findings import Finding
from social_agent.audit.issues import (
    FINGERPRINT_PREFIX,
    extract_fingerprints,
    issue_body,
    issue_title,
    new_findings,
)


def _finding(**kwargs: object) -> Finding:
    base = {
        "rule_id": "PYSEC-1",
        "path": "pkg@1.0",
        "message": "boom",
        "source": "pip-audit",
        "extra": {},
    }
    base.update(kwargs)
    return Finding(**base)  # type: ignore[arg-type]


def test_issue_title_and_body_embed_fingerprint_marker() -> None:
    f = _finding()
    title = issue_title(f)
    assert title.startswith("[FIX] audit:")
    assert "PYSEC-1" in title
    body = issue_body(f)
    assert f"{FINGERPRINT_PREFIX}{f.fingerprint} -->" in body
    assert "pip-audit" in body


def test_extract_fingerprints_from_issue_bodies() -> None:
    f = _finding()
    bodies = [
        issue_body(f),
        "unrelated issue",
        f"<!-- audit-fingerprint: {'a' * 32} -->",
    ]
    fps = extract_fingerprints(bodies)
    assert f.fingerprint in fps
    assert "a" * 32 in fps


def test_new_findings_skips_open_fingerprints() -> None:
    a = _finding(rule_id="A")
    b = _finding(rule_id="B")
    assert new_findings([a, b], {a.fingerprint}) == [b]
