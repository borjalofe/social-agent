"""Run SCA (pip-audit) and SAST (ruff S*) scanners."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from social_agent.audit.findings import Finding, findings_from_pip_audit, findings_from_ruff


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return Path.cwd()


def _run_json(cmd: list[str]) -> object:
    # argv is a fixed scanner invocation controlled by this module (not user input).
    proc = subprocess.run(  # noqa: S603
        cmd, cwd=_repo_root(), capture_output=True, text=True, check=False
    )
    stdout = (proc.stdout or "").strip()
    if not stdout:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"command produced no JSON (exit {proc.returncode}): {cmd}\n{stderr}")
    return json.loads(stdout)


def _relativize_ruff_paths(payload: object) -> object:
    if not isinstance(payload, list):
        return payload
    root = _repo_root()
    out: list[object] = []
    for item in payload:
        if not isinstance(item, dict):
            out.append(item)
            continue
        copy = dict(item)
        raw = str(copy.get("filename") or "")
        try:
            copy["filename"] = str(Path(raw).resolve().relative_to(root))
        except ValueError:
            copy["filename"] = raw
        out.append(copy)
    return out


def collect_pip_audit() -> list[Finding]:
    data = _run_json(
        ["pip-audit", "-f", "json", "--progress-spinner", "off"],
    )
    return findings_from_pip_audit(data)


def collect_ruff_security() -> list[Finding]:
    data = _run_json(
        [
            "ruff",
            "check",
            "--select",
            "S",
            "--output-format",
            "json",
            "src",
        ],
    )
    return findings_from_ruff(_relativize_ruff_paths(data))


def collect_all() -> list[Finding]:
    findings = [*collect_pip_audit(), *collect_ruff_security()]
    seen: set[str] = set()
    unique: list[Finding] = []
    for finding in findings:
        if finding.fingerprint in seen:
            continue
        seen.add(finding.fingerprint)
        unique.append(finding)
    return unique
