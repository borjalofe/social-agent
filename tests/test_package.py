"""Smoke: package is importable."""

from __future__ import annotations

import social_agent


def test_package_exposes_version() -> None:
    assert isinstance(social_agent.__version__, str)
    assert social_agent.__version__
