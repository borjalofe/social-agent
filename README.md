# social-agent

Multi-user editorial agents behind Siren. Host: [github.com/borjalofe/social-agent](https://github.com/borjalofe/social-agent).

## Requirements

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/)

## Local quality gates (same as PR CI)

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run pip-audit
```

PR / `main` CI: `.github/workflows/ci.yml`.

## Daily audit

Scheduled workflow (`.github/workflows/audit.yml`, 06:00 UTC + `workflow_dispatch`) runs SCA (`pip-audit`) and SAST (`ruff` rule set `S`), then opens **one GitHub issue per new finding**. Dedupe uses a fingerprint of rule/id + path + normalized message embedded in the issue body (`audit-finding` label).

Dry-run locally (no GitHub calls):

```bash
uv run python -m social_agent.audit --dry-run
```
