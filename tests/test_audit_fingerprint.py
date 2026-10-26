"""Fingerprint: rule/id + path + normalized message."""

from __future__ import annotations

from social_agent.audit.fingerprint import fingerprint, normalize_message


def test_normalize_message_collapses_whitespace_and_case() -> None:
    assert normalize_message("  Foo\nBAR  baz ") == "foo bar baz"


def test_fingerprint_is_stable_for_same_inputs() -> None:
    a = fingerprint("PYSEC-1", "requests@2.0", "Cross site scripting")
    b = fingerprint("PYSEC-1", "requests@2.0", "cross   site\nscripting")
    assert a == b
    assert len(a) == 32


def test_fingerprint_changes_when_rule_path_or_message_changes() -> None:
    base = fingerprint("PYSEC-1", "pkg@1", "msg")
    assert fingerprint("PYSEC-2", "pkg@1", "msg") != base
    assert fingerprint("PYSEC-1", "pkg@2", "msg") != base
    assert fingerprint("PYSEC-1", "pkg@1", "other") != base
