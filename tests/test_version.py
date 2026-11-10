"""The package's version is the specification's: one number in the changelog, the package and
every analysis.json (2026-11-10: 0.4.3 shipped with the package still saying 0.4.2)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lumiere.spec import SPEC_VERSION


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib is new in Python 3.11")
def test_the_package_version_is_the_spec_version() -> None:
    import tomllib

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    assert tomllib.loads(pyproject.read_text())["project"]["version"] == SPEC_VERSION
    changelog = (pyproject.parent / "CHANGELOG.md").read_text()
    assert f"## {SPEC_VERSION} " in changelog
