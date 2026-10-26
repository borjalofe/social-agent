"""Contract for daily audit GitHub Actions workflow (issue #5)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "audit.yml"


def test_audit_workflow_exists() -> None:
    assert WORKFLOW.is_file()


def test_audit_workflow_is_scheduled_and_opens_issues() -> None:
    cfg = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    on = cfg.get("on", cfg.get(True))
    assert on is not None
    assert "schedule" in on
    assert "workflow_dispatch" in on
    crons = [entry["cron"] for entry in on["schedule"]]
    assert crons, "expected at least one cron schedule"
    perms = cfg.get("permissions") or {}
    assert perms.get("issues") == "write"
    job = next(iter(cfg["jobs"].values()))
    script = "\n".join(
        step.get("run", "") for step in job["steps"] if isinstance(step, dict)
    ).lower()
    assert "social_agent.audit" in script or "social-agent.audit" in script
