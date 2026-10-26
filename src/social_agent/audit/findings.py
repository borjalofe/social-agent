"""Normalize scanner outputs into Finding values."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from social_agent.audit.fingerprint import fingerprint as make_fingerprint


@dataclass(frozen=True)
class Finding:
    rule_id: str
    path: str
    message: str
    source: str
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        return make_fingerprint(self.rule_id, self.path, self.message)


def findings_from_pip_audit(payload: Any) -> list[Finding]:
    deps: list[Any]
    if isinstance(payload, dict):
        deps = list(payload.get("dependencies") or [])
    elif isinstance(payload, list):
        deps = payload
    else:
        return []

    out: list[Finding] = []
    for dep in deps:
        if not isinstance(dep, dict):
            continue
        name = str(dep.get("name") or "")
        version = str(dep.get("version") or "")
        path = f"{name}@{version}" if version else name
        for vuln in dep.get("vulns") or []:
            if not isinstance(vuln, dict):
                continue
            rule_id = str(vuln.get("id") or "").strip()
            if not rule_id:
                continue
            message = str(vuln.get("description") or rule_id)
            extra = {
                "fix_versions": list(vuln.get("fix_versions") or []),
                "aliases": list(vuln.get("aliases") or []),
            }
            out.append(
                Finding(
                    rule_id=rule_id,
                    path=path,
                    message=message,
                    source="pip-audit",
                    extra=extra,
                )
            )
    return out


def findings_from_ruff(payload: Any) -> list[Finding]:
    if not isinstance(payload, list):
        return []
    out: list[Finding] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        rule_id = str(item.get("code") or "").strip()
        path = str(item.get("filename") or "").strip()
        message = str(item.get("message") or rule_id)
        if not rule_id or not path:
            continue
        out.append(
            Finding(
                rule_id=rule_id,
                path=path,
                message=message,
                source="ruff-s",
                extra={"location": item.get("location") or {}},
            )
        )
    return out
