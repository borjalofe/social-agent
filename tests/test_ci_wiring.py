"""Contract for GitHub Actions CI seed (issue #4)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_exists() -> None:
    assert WORKFLOW.is_file()


def test_ci_workflow_runs_lint_and_tests() -> None:
    cfg = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML may parse unquoted `on:` as boolean True
    on = cfg.get("on", cfg.get(True))
    assert on is not None
    assert "pull_request" in on
    assert "push" in on
    job = next(iter(cfg["jobs"].values()))
    assert job["runs-on"] == "ubuntu-latest"
    script = "\n".join(
        step.get("run", "") for step in job["steps"] if isinstance(step, dict)
    ).lower()
    assert "ruff" in script
    assert "pytest" in script
    assert "pip-audit" in script or "audit" in script
