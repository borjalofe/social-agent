"""Smoke: package is importable."""

from __future__ import annotations

import social_agent


def test_package_exposes_version() -> None:
    assert social_agent.__version__ == "0.3.0"
