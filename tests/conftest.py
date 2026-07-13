"""
Shared pytest fixtures.
"""

import json

import pytest


@pytest.fixture
def write_json(tmp_path):
    """Write JSON to a file in tmp_path; returns tmp_path for use as DATA_DIR."""

    def _write(filename: str, data) -> "Path":  # noqa: F821
        (tmp_path / filename).write_text(json.dumps(data))
        return tmp_path

    return _write
