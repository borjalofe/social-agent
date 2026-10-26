# social-agent

Multi-user editorial agents behind Siren. Host: [github.com/borjalofe/social-agent](https://github.com/borjalofe/social-agent).

## Requirements

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/)

## Local quality gates (same as CI)

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run pip-audit
```

CI runs on every pull request and on pushes to `main` (`.github/workflows/ci.yml`).
