"""Minimal GitHub Issues API client (stdlib only)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class GitHubError(RuntimeError):
    pass


class GitHubIssues:
    def __init__(
        self,
        token: str | None = None,
        repository: str | None = None,
        api_url: str = "https://api.github.com",
    ) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.repository = repository or os.environ.get("GITHUB_REPOSITORY")
        self.api_url = api_url.rstrip("/")
        if not self.token:
            raise GitHubError("GITHUB_TOKEN (or GH_TOKEN) is required")
        if not self.repository:
            raise GitHubError("GITHUB_REPOSITORY is required (owner/repo)")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        url = f"{self.api_url}/repos/{self.repository}{path}"
        if not url.startswith(f"{self.api_url}/"):
            raise GitHubError(f"refusing non-API URL: {url}")
        data = None if body is None else json.dumps(body).encode("utf-8")
        # URL is built from configured api_url + repo path (HTTPS GitHub API only).
        req = urllib.request.Request(  # noqa: S310
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "social-agent-audit",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitHubError(f"{method} {path} -> {exc.code}: {detail}") from exc

    def list_open_issue_bodies(self, label: str) -> list[str]:
        bodies: list[str] = []
        page = 1
        while True:
            qs = urllib.parse.urlencode(
                {
                    "state": "open",
                    "labels": label,
                    "per_page": 100,
                    "page": page,
                }
            )
            batch = self._request("GET", f"/issues?{qs}")
            if not isinstance(batch, list) or not batch:
                break
            for item in batch:
                if not isinstance(item, dict):
                    continue
                if item.get("pull_request"):
                    continue
                bodies.append(str(item.get("body") or ""))
            if len(batch) < 100:
                break
            page += 1
        return bodies

    def create_issue(self, title: str, body: str, labels: list[str]) -> dict[str, Any]:
        result = self._request(
            "POST",
            "/issues",
            {"title": title, "body": body, "labels": labels},
        )
        if not isinstance(result, dict):
            raise GitHubError("unexpected create issue response")
        return result

    def ensure_label(self, name: str, color: str, description: str) -> None:
        try:
            self._request(
                "POST",
                "/labels",
                {"name": name, "color": color, "description": description},
            )
        except GitHubError as exc:
            if "already_exists" in str(exc) or "422" in str(exc):
                return
            raise
