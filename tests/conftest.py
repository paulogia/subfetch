"""Pytest fixtures for subfetch tests."""

import pytest
from pathlib import Path


@pytest.fixture
def temp_output_dir(tmp_path):
    """Provide a temporary output directory."""
    output = tmp_path / "subtitles"
    output.mkdir()
    return output
