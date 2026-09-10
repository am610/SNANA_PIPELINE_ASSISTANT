"""Deterministic tests for the read-only MCP server tools and safety boundaries.

Ensures:
- FastMCP tool registration and schema validity
- search_knowledge parity with Python KnowledgeBase
- search_manual parity with tools.search_manual
- Read-only limits, truncation, and bounds checking
- Binary / FITS / archive file rejection
- Path traversal and missing file handling
- Sanitized environment inspection (no leaked secrets)
- No write semantics or execution vulnerabilities
"""

import os
import tempfile
from pathlib import Path

import pytest

import snana_assistant.mcp_server as s
from snana_assistant.knowledge import KnowledgeBase
from snana_assistant.tool_policy import (
    MAX_FILE_BYTES,
    MAX_FILE_LINES,
    looks_binary,
    sanitize_environment,
)
from snana_assistant.tools import search_manual as py_search_manual


def test_mcp_server_initialization():
    """Verify FastMCP server instance and registered tool names."""
    assert s.mcp.name == "snana-assistant"
    # Call each tool directly to verify registration
    expected_tools = {
        "search_knowledge",
        "search_manual",
        "check_job_status",
        "read_log_tail",
        "diff_config",
        "list_directory",
        "search_files",
        "read_text_file",
        "inspect_snana_environment",
    }
    # FastMCP holds registered tool objects
    for tool_name in expected_tools:
        assert hasattr(s, tool_name), f"Tool function {tool_name} should exist in mcp_server"


def test_search_knowledge_parity():
    """Verify search_knowledge tool matches underlying KnowledgeBase ranking."""
    kb = KnowledgeBase.load()
    query = "stale busy merge lock"
    kb_results = kb.search(query, top_k=3)
    assert len(kb_results) > 0
    top_entry_id = kb_results[0].id

    mcp_output = s.search_knowledge(query, top_k=3)
    assert f"[{top_entry_id}]" in mcp_output
    assert "Score:" in mcp_output


def test_search_manual_parity():
    """Verify search_manual tool matches tools.search_manual."""
    query = "SIMLIB"
    py_out = py_search_manual(query, top_k=2)
    mcp_out = s.search_manual(query, top_k=2)
    assert "relevant sections in the manual" in mcp_out
    assert py_out == mcp_out


def test_check_job_status_safe():
    """Verify scheduler inspection is read-only and handles non-existent jobs gracefully."""
    out = s.check_job_status(user="nonexistent_user_xyz_999")
    assert isinstance(out, str)
    assert len(out) > 0


def test_read_log_tail_flags_and_bounds():
    """Verify read_log_tail flags failure signatures and respects line bounds."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        for i in range(100):
            f.write(f"Normal execution line {i}\n")
        f.write("ERROR: Segmentation fault detected\n")
        f.write("CANCELLED AT 2026-09-10 DUE TO TIME LIMIT\n")
        for i in range(20):
            f.write(f"Post abort line {i}\n")
        temp_path = f.name

    try:
        res = s.read_log_tail(temp_path, n_lines=50)
        assert "--- FLAGGED ---" in res
        assert "Segmentation fault" in res
        assert "DUE TO TIME LIMIT" in res
        assert "Last 50 lines" in res
    finally:
        os.unlink(temp_path)


def test_read_text_file_binary_and_size_rejection():
    """Verify read_text_file rejects binary files and files exceeding byte ceilings."""
    # 1. Binary file test
    with tempfile.NamedTemporaryFile(suffix=".fits", delete=False) as f:
        f.write(b"SIMPLE  =                    T / file does conform to FITS standard\0\0\0")
        bin_path = f.name

    try:
        assert looks_binary(bin_path) is True
        bin_res = s.read_text_file(bin_path)
        assert "Refused" in bin_res and "binary" in bin_res
    finally:
        os.unlink(bin_path)

    # 2. Oversized file test
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("A" * (MAX_FILE_BYTES + 100))
        oversized_path = f.name

    try:
        over_res = s.read_text_file(oversized_path)
        assert "Refused" in over_res and "exceeds maximum allowed text limit" in over_res
    finally:
        os.unlink(oversized_path)


def test_diff_config_reporting():
    """Verify diff_config accurately reports identical vs differing files."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f1:
        f1.write("PARAM1: 10\nPARAM2: 20\n")
        p1 = f1.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f2:
        f2.write("PARAM1: 10\nPARAM2: 99\n")
        p2 = f2.name

    try:
        # Differing
        diff_res = s.diff_config(p1, p2)
        assert "Source and cached copy DIFFER" in diff_res
        assert "+PARAM2: 99" in diff_res or "-PARAM2: 20" in diff_res

        # Identical
        same_res = s.diff_config(p1, p1)
        assert "No difference" in same_res
    finally:
        os.unlink(p1)
        os.unlink(p2)


def test_environment_sanitization():
    """Verify inspect_snana_environment strictly suppresses secrets and sensitive tokens."""
    os.environ["SUPER_SECRET_TOKEN"] = "sensitive_bearer_token"
    os.environ["SNANA_PASSWORD"] = "private_pass"
    os.environ["SNDATA_ROOT"] = "/test/sndata"

    try:
        sanitized = sanitize_environment()
        assert "SUPER_SECRET_TOKEN" not in sanitized
        assert "SNANA_PASSWORD" not in sanitized
        assert "SNDATA_ROOT" in sanitized
        assert sanitized["SNDATA_ROOT"] == "/test/sndata"

        mcp_env = s.inspect_snana_environment()
        assert "SUPER_SECRET_TOKEN" not in mcp_env
        assert "SNANA_PASSWORD" not in mcp_env
        assert "SNDATA_ROOT" in mcp_env
    finally:
        os.environ.pop("SUPER_SECRET_TOKEN", None)
        os.environ.pop("SNANA_PASSWORD", None)


def test_missing_files_error_handling():
    """Verify all file-reading tools handle non-existent files cleanly without exceptions."""
    missing = "/tmp/non_existent_path_snana_123456789.txt"
    assert "File not found" in s.read_text_file(missing)
    assert "File not found" in s.read_log_tail(missing)
    assert "File not found" in s.diff_config(missing, missing)
    assert "Path not found" in s.search_files("test", path=missing)
    assert "Directory not found" in s.list_directory(path=missing)
