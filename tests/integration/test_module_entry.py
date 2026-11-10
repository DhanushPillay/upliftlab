"""Module entry point smoke test."""

from __future__ import annotations

import subprocess
import sys


def test_python_m_upliftlab_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "upliftlab", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "upliftlab" in result.stdout
