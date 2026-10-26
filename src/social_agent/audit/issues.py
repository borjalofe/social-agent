"""GitHub issue title/body helpers and open-fingerprint dedupe."""

from __future__ import annotations

import re
from collections.abc import Iterable

from social_agent.audit.findings import Finding

FINGERPRINT_PREFIX = "<!-- audit-fingerprint: "
_FP_RE = re.compile(r"<!--\s*audit-fingerprint:\s*([0-9a-f]{32})\s*-->", re.I)


def issue_title(finding: Finding) -> str:
    return f"[FIX] audit: {finding.rule_id} in {finding.path}"


def issue_body(finding: Finding) -> str:
    fix = finding.extra.get("fix_versions") or []
    aliases = finding.extra.get("aliases") or []
    lines = [
        f"{FINGERPRINT_PREFIX}{finding.fingerprint} -->",
        "",
        "## Finding",
        f"- Source: `{finding.source}`",
        f"- Rule / id: `{finding.rule_id}`",
        f"- Path: `{finding.path}`",
        f"- Message: {finding.message}",
    ]
    if aliases:
        lines.append(f"- Aliases: {', '.join(f'`{a}`' for a in aliases)}")
    if fix:
        lines.append(f"- Fix versions: {', '.join(f'`{v}`' for v in fix)}")
    lines.extend(
        [
            "",
            "## Notes",
            "Opened by the daily audit workflow. One issue per new fingerprint;",
            "reopening after close is intentional if the finding returns.",
        ]
    )
    return "\n".join(lines) + "\n"


def extract_fingerprints(bodies: Iterable[str]) -> set[str]:
    found: set[str] = set()
    for body in bodies:
        for match in _FP_RE.finditer(body or ""):
            found.add(match.group(1).lower())
    return found


def new_findings(findings: list[Finding], open_fingerprints: set[str]) -> list[Finding]:
    open_norm = {fp.lower() for fp in open_fingerprints}
    return [f for f in findings if f.fingerprint.lower() not in open_norm]
