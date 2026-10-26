"""CLI: collect findings and open one GitHub issue per new fingerprint."""

from __future__ import annotations

import argparse
import sys

from social_agent.audit.collect import collect_all
from social_agent.audit.github import GitHubIssues
from social_agent.audit.issues import extract_fingerprints, issue_body, issue_title, new_findings

AUDIT_LABEL = "audit-finding"
ISSUE_LABELS = [AUDIT_LABEL, "category:security"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print findings that would open issues; do not call GitHub",
    )
    args = parser.parse_args(argv)

    findings = collect_all()
    if args.dry_run:
        print(f"collected {len(findings)} finding(s)")
        for f in findings:
            print(f"- {f.fingerprint} {f.source} {f.rule_id} {f.path}")
        return 0

    gh = GitHubIssues()
    gh.ensure_label(
        AUDIT_LABEL,
        color="B60205",
        description="Opened by daily audit CI (fingerprint dedupe)",
    )
    open_fps = extract_fingerprints(gh.list_open_issue_bodies(AUDIT_LABEL))
    to_open = new_findings(findings, open_fps)
    print(f"collected={len(findings)} open_fingerprints={len(open_fps)} to_open={len(to_open)}")
    for finding in to_open:
        created = gh.create_issue(
            title=issue_title(finding),
            body=issue_body(finding),
            labels=ISSUE_LABELS,
        )
        print(f"opened #{created.get('number')} {issue_title(finding)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
