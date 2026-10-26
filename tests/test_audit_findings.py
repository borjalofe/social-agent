"""Parse scanner JSON into Finding values."""

from __future__ import annotations

from social_agent.audit.findings import (
    Finding,
    findings_from_pip_audit,
    findings_from_ruff,
)


def test_findings_from_pip_audit_skips_clean_deps() -> None:
    payload = {
        "dependencies": [
            {"name": "clean", "version": "1.0", "vulns": []},
            {
                "name": "evil",
                "version": "0.1",
                "vulns": [
                    {
                        "id": "PYSEC-2020-1",
                        "description": "Bad thing",
                        "fix_versions": ["0.2"],
                        "aliases": ["CVE-2020-1"],
                    }
                ],
            },
        ]
    }
    findings = findings_from_pip_audit(payload)
    assert len(findings) == 1
    f = findings[0]
    assert f == Finding(
        rule_id="PYSEC-2020-1",
        path="evil@0.1",
        message="Bad thing",
        source="pip-audit",
        extra={"fix_versions": ["0.2"], "aliases": ["CVE-2020-1"]},
    )
    assert f.fingerprint


def test_findings_from_pip_audit_accepts_bare_list() -> None:
    payload = [
        {
            "name": "x",
            "version": "1",
            "vulns": [{"id": "GHSA-1", "description": "x"}],
        }
    ]
    assert len(findings_from_pip_audit(payload)) == 1


def test_findings_from_ruff_maps_security_diagnostics() -> None:
    payload = [
        {
            "code": "S105",
            "filename": "src/social_agent/x.py",
            "message": "Possible hardcoded password assigned to: secret",
            "location": {"row": 3, "column": 1},
        }
    ]
    findings = findings_from_ruff(payload)
    assert len(findings) == 1
    assert findings[0].rule_id == "S105"
    assert findings[0].path == "src/social_agent/x.py"
    assert findings[0].source == "ruff-s"


def test_collect_all_dedupes_identical_fingerprints(monkeypatch: object) -> None:
    from social_agent.audit import collect as collect_mod
    from social_agent.audit.findings import Finding

    twin = Finding(
        rule_id="S105",
        path="src/x.py",
        message="secret",
        source="ruff-s",
    )

    monkeypatch.setattr(collect_mod, "collect_pip_audit", lambda: [])
    monkeypatch.setattr(collect_mod, "collect_ruff_security", lambda: [twin, twin])
    assert collect_mod.collect_all() == [twin]
