from __future__ import annotations

import os
import stat
import textwrap
import time
import uuid
from pathlib import Path
from unittest import mock

import pytest

import toc_markdown.cli as cli_module


def _write(tmp_path: Path, name: str, content: str) -> Path:
    target = tmp_path / name
    target.write_text(textwrap.dedent(content), encoding="utf-8")
    return target


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="Symlink support is required")
def test_symlink_rejected(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = _write(
        tmp_path,
        "source.md",
        """
        ## Heading
        """,
    )
    link = tmp_path / "alias.md"
    try:
        os.symlink(source, link, target_is_directory=False)
    except OSError as error:  # pragma: no cover - platform dependent
        pytest.skip(f"Unable to create symlink: {error}")

    result = cli_runner.invoke(cli_module.cli, [str(link)])
    assert result.exit_code != 0
    assert "Symlinks" in result.output


def test_path_traversal_prevented(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outside = tmp_path.parent / f"outside-{uuid.uuid4().hex}.md"
    outside.write_text("## Outside\n", encoding="utf-8")

    try:
        result = cli_runner.invoke(cli_module.cli, [str(outside)])
        assert result.exit_code != 0
        assert "outside of the working directory" in result.output
    finally:
        outside.unlink(missing_ok=True)


def test_file_size_limit_enforced(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TOC_MARKDOWN_MAX_FILE_SIZE", "10")
    target = _write(
        tmp_path,
        "large.md",
        """
        ## Heading
        """,
    )
    target.write_text("X" * 20, encoding="utf-8")

    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code != 0
    assert "maximum allowed size" in str(result.exception)


def test_line_length_limit_enforced(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Create a file with a line exceeding MAX_LINE_LENGTH (10,000 characters)
    target = _write(
        tmp_path,
        "long_line.md",
        """
        ## Heading
        """,
    )
    # Create content with a line that's 10,001 characters long
    long_line = "X" * 10_001
    target.write_text(f"## Valid Heading\n{long_line}\n## Another Heading\n", encoding="utf-8")

    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code != 0
    assert "maximum allowed length" in str(result.exception)
    assert "10000" in str(result.exception)


def test_line_length_within_limit_allowed(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Create a file with a line at exactly MAX_LINE_LENGTH (10,000 characters)
    target = _write(
        tmp_path,
        "max_line.md",
        """
        ## Heading
        """,
    )
    # Create content with a line that's exactly 10,000 characters (should pass)
    max_line = "X" * 10_000
    target.write_text(f"## Valid Heading\n{max_line}\n## Another Heading\n", encoding="utf-8")

    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code == 0



def test_line_length_limit_enforced_without_toc_end(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "unclosed_toc.md",
        """
        ## Header 1
        """,
    )
    long_line = "X" * 20_000
    content = f"""## Header 1

<!-- TOC -->
## Table of Contents

{long_line}

## Header 2
"""
    target.write_text(content, encoding="utf-8")

    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code != 0
    assert "maximum allowed length" in str(result.exception)


def test_line_length_limit_ignores_code_blocks(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Lines inside code blocks should NOT be subject to line length limit
    target = _write(
        tmp_path,
        "code_block_long_line.md",
        """
        ## Valid Header
        """,
    )
    # Create a file with a very long line (20,000 chars) inside a code block
    long_line = "X" * 20_000
    content = f"## Header\n\n```python\n{long_line}\n```\n\n## Another Header\n"
    target.write_text(content, encoding="utf-8")

    result = cli_runner.invoke(cli_module.cli, [str(target)])
    # Should succeed because the long line is inside a code block
    assert result.exit_code == 0


def test_line_length_limit_configurable(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Test that the line length limit can be configured via environment variable
    monkeypatch.setenv("TOC_MARKDOWN_MAX_LINE_LENGTH", "50")
    target = _write(
        tmp_path,
        "custom_limit.md",
        """
        ## Heading
        """,
    )
    # Create a line with 51 characters (exceeds custom limit of 50)
    long_line = "X" * 51
    target.write_text(f"## Header\n{long_line}\n", encoding="utf-8")

    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code != 0
    assert "maximum allowed length" in str(result.exception)
    assert "50" in str(result.exception)


def test_line_length_limit_ignores_existing_toc(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # A malicious TOC with a very long line should not block TOC updates
    target = _write(
        tmp_path,
        "malicious_toc.md",
        """
        ## Header 1
        """,
    )
    # Create a TOC with a 20,000 character line inside it
    long_toc_line = "X" * 20_000
    content = f"""## Header 1

<!-- TOC -->
## Table of Contents

{long_toc_line}
<!-- /TOC -->

## Header 2
## Header 3
"""
    target.write_text(content, encoding="utf-8")

    # Should succeed - the tool should update/rewrite the TOC despite the malicious line
    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code == 0


def test_header_count_limit_enforced(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Create a file with more than MAX_HEADERS (10,000) headers
    target = _write(
        tmp_path,
        "many_headers.md",
        """
        # Initial content
        """,
    )
    # Create content with 10,001 headers
    many_headers = "## Header\n" * 10_001
    target.write_text(many_headers, encoding="utf-8")

    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code != 0
    assert "too many headers" in str(result.exception)
    assert "10000" in str(result.exception)


def test_header_count_within_limit_allowed(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Create a file with exactly MAX_HEADERS (10,000) headers
    target = _write(
        tmp_path,
        "max_headers.md",
        """
        # Initial content
        """,
    )
    # Create content with exactly 10,000 headers (should pass)
    max_headers = "## Header\n" * 10_000
    target.write_text(max_headers, encoding="utf-8")

    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code == 0


def test_permissions_preserved_on_update(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "permissions.md",
        """
        <!-- TOC -->
        ## Table of Contents

        1. Old entry
        <!-- /TOC -->
        ## Heading
        ### Details
        """,
    )
    desired_mode = 0o640
    os.chmod(target, desired_mode)

    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code == 0
    assert stat.S_IMODE(target.stat().st_mode) == desired_mode


def test_atime_preserved_mtime_updated(cli_runner, tmp_path, monkeypatch):
    """Verify atime is preserved but mtime reflects the actual modification."""
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "timestamps.md",
        """
        <!-- TOC -->
        ## Table of Contents

        1. Old entry
        <!-- /TOC -->
        ## Heading
        ### Details
        """,
    )

    # Set specific timestamps (use past times to avoid edge cases)
    specific_atime = time.time() - 86400  # 1 day ago
    specific_mtime = time.time() - 3600   # 1 hour ago
    os.utime(target, times=(specific_atime, specific_mtime))

    # Get original timestamps with nanosecond precision
    original_stat = target.stat()
    original_atime_ns = original_stat.st_atime_ns
    original_mtime_ns = original_stat.st_mtime_ns

    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code == 0

    # Verify atime is preserved but mtime has been updated
    updated_stat = target.stat()
    assert updated_stat.st_atime_ns == original_atime_ns
    # mtime should be NEWER than original (file was actually modified)
    assert updated_stat.st_mtime_ns > original_mtime_ns


@pytest.mark.skipif(os.geteuid() != 0 if hasattr(os, "geteuid") else True, reason="Requires root privileges")
def test_ownership_preserved_when_privileged(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "ownership.md",
        """
        <!-- TOC -->
        ## Table of Contents

        1. Old entry
        <!-- /TOC -->
        ## Heading
        ### Details
        """,
    )

    # Get current ownership
    original_stat = target.stat()
    original_uid = original_stat.st_uid
    original_gid = original_stat.st_gid

    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code == 0

    # Verify ownership is preserved
    updated_stat = target.stat()
    assert updated_stat.st_uid == original_uid
    assert updated_stat.st_gid == original_gid


@pytest.mark.skipif(not hasattr(os, "chown"), reason="Requires os.chown support")
def test_ownership_fails_gracefully_when_unprivileged(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "ownership_unprivileged.md",
        """
        <!-- TOC -->
        ## Table of Contents

        1. Old entry
        <!-- /TOC -->
        ## Heading
        ### Details
        """,
    )

    # Mock os.chown to raise PermissionError
    original_chown = os.chown
    def mock_chown(*args, **kwargs):
        raise PermissionError("Operation not permitted")

    with mock.patch("os.chown", side_effect=mock_chown):
        result = cli_runner.invoke(cli_module.cli, [str(target)])

    # Should succeed despite chown failure
    assert result.exit_code == 0

    # Verify warning message was displayed
    assert "Warning: Could not preserve file ownership" in result.output
    assert "requires elevated privileges" in result.output

    # Verify file was still updated (check TOC content changed)
    content = target.read_text()
    assert "Heading" in content
    assert "Details" in content


def test_ownership_skipped_when_unsupported(cli_runner, tmp_path, monkeypatch):
    """Test that ownership preservation is skipped on platforms without st_uid/st_gid (e.g., Windows)."""
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "ownership_windows.md",
        """
        <!-- TOC -->
        ## Table of Contents

        1. Old entry
        <!-- /TOC -->
        ## Heading
        ### Details
        """,
    )

    # Mock stat_result to not have st_uid/st_gid attributes (Windows behavior)
    original_stat = os.stat
    def mock_stat(path):
        result = original_stat(path)
        # Create a new stat_result without st_uid and st_gid
        # We'll mock getattr to return None for these attributes
        return result

    with mock.patch("toc_markdown.cli.getattr", side_effect=lambda obj, attr, default=None: None if attr in ("st_uid", "st_gid") else getattr(obj, attr, default)):
        result = cli_runner.invoke(cli_module.cli, [str(target)])

    # Should succeed and not attempt chown
    assert result.exit_code == 0

    # Should not display ownership warning (chown never attempted)
    assert "Warning: Could not preserve file ownership" not in result.output

    # Verify file was still updated
    content = target.read_text()
    assert "Heading" in content
    assert "Details" in content


def test_invalid_utf8_handling(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "broken.md"
    target.write_bytes(b"\xff\xfe## Heading\n")

    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code != 0
    assert "Invalid UTF-8" in str(result.exception)


def test_race_condition_detection(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "race.md",
        """
        <!-- TOC -->
        ## Table of Contents

        1. Old entry
        <!-- /TOC -->
        ## Heading
        """,
    )

    original_parse = cli_module.parse_file

    def _parse_and_mutate(path: Path, max_line_length: int):
        result = original_parse(path, max_line_length)
        existing = path.read_text(encoding="utf-8")
        path.write_text(existing + "\n## Mutated\n", encoding="utf-8")
        return result

    monkeypatch.setattr(cli_module, "parse_file", _parse_and_mutate)
    result = cli_runner.invoke(cli_module.cli, [str(target)])

    assert result.exit_code != 0
    assert "changed during processing" in str(result.exception)
