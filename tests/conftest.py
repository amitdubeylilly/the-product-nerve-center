"""
Shared pytest fixtures.
"""

import json
import os

import pytest

# server.py fetches roster/deps from the data server at import time when
# MCP_DATA_URL is set. Ensure tests never touch the network at import.
os.environ.pop("MCP_DATA_URL", None)


@pytest.fixture
def write_json(tmp_path):
    """Write JSON to a file in tmp_path; returns tmp_path for use as DATA_DIR."""

    def _write(filename: str, data) -> "Path":  # noqa: F821
        (tmp_path / filename).write_text(json.dumps(data))
        return tmp_path

    return _write
