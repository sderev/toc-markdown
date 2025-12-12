from __future__ import annotations

import os
import socket
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


def _error_text(result) -> str:
    """Return combined stdout and exception text for assertions."""
    return f"{result.output}{result.exception}"


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
    error_text = _error_text(result)
    assert "maximum allowed size" in error_text


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
    error_text = _error_text(result)
    assert "maximum allowed length" in error_text
    assert "10000" in error_text


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
    error_text = _error_text(result)
    assert "maximum allowed length" in error_text


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
    error_text = _error_text(result)
    assert "maximum allowed length" in error_text
    assert "50" in error_text


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


def test_toc_markers_in_code_blocks_dont_bypass_line_length(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # CRITICAL SECURITY TEST: Fake TOC markers spanning code blocks create intervals
    # in pre-computation, causing lines between them to bypass validation even if
    # those lines are outside code blocks.
    #
    # Attack scenario:
    # ```
    # <!-- TOC -->    <- Line 1: Fake start marker inside code
    # ```
    # [LONG LINE]     <- Line 3: >10k chars, NOT in code block, should trigger error
    # ```
    # <!-- /TOC -->   <- Line 5: Fake end marker inside code
    # ```
    #
    # Buggy behavior: Pre-computation creates interval (1, 5), marks line 3 as "in TOC",
    # skips validation, CLI succeeds.
    # Fixed behavior: Pre-computation ignores markers in code blocks, no interval created,
    # line 3 triggers validation error, CLI fails.

    target = _write(
        tmp_path,
        "fake_toc_attack.md",
        """
        ## Header 1
        """,
    )

    # Create a >10k character line that should fail validation
    long_line = "X" * 10_001

    # Place fake markers in code blocks with long line between them
    content = f"""## Header 1

```
<!-- TOC -->
```
{long_line}
```
<!-- /TOC -->
```

## Header 2
"""
    target.write_text(content, encoding="utf-8")

    # Should FAIL with line length error (fixed code)
    # Would succeed on buggy code (line incorrectly marked as "in TOC")
    result = cli_runner.invoke(cli_module.cli, [str(target)])
    assert result.exit_code != 0
    error_text = _error_text(result)
    assert "maximum allowed length" in error_text
    assert "10000" in error_text


def test_long_lines_in_code_blocks_with_fake_markers_allowed(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Complementary test: Long lines inside code blocks should be exempt from validation,
    # even when fake TOC markers are present. This ensures the fix doesn't create false positives.
    target = _write(
        tmp_path,
        "code_block_long_line.md",
        """
        ## Header 1
        """,
    )

    # Create a >10k character line INSIDE a code block
    long_line = "X" * 20_000

    content = f"""## Header 1

```
<!-- TOC -->
{long_line}
<!-- /TOC -->
```

## Header 2
"""
    target.write_text(content, encoding="utf-8")

    # Should succeed - lines inside code blocks are always exempt
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
    error_text = _error_text(result)
    assert "too many headers" in error_text
    assert "10000" in error_text


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
    specific_mtime = time.time() - 3600  # 1 hour ago
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


@pytest.mark.skipif(
    os.geteuid() != 0 if hasattr(os, "geteuid") else True, reason="Requires root privileges"
)
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

    with mock.patch(
        "toc_markdown.filesystem.getattr",
        side_effect=lambda obj, attr, default=None: None
        if attr in ("st_uid", "st_gid")
        else getattr(obj, attr, default),
    ):
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
    assert "Invalid UTF-8" in _error_text(result)


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

    def _parse_and_mutate(path: Path, max_line_length: int, config=None):
        result = original_parse(path, max_line_length, config)
        existing = path.read_text(encoding="utf-8")
        path.write_text(existing + "\n## Mutated\n", encoding="utf-8")
        return result

    monkeypatch.setattr(cli_module, "parse_file", _parse_and_mutate)
    result = cli_runner.invoke(cli_module.cli, [str(target)])

    assert result.exit_code != 0
    assert "changed during processing" in _error_text(result)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="mkfifo not available")
def test_fifo_rejected(cli_runner, tmp_path, monkeypatch):
    """Test that FIFOs (named pipes) are rejected to prevent DoS via blocking reads."""
    monkeypatch.chdir(tmp_path)
    fifo_path = tmp_path / "malicious.md"

    try:
        os.mkfifo(fifo_path)
    except OSError as error:  # pragma: no cover - platform dependent
        pytest.skip(f"Unable to create FIFO: {error}")

    result = cli_runner.invoke(cli_module.cli, [str(fifo_path)])
    assert result.exit_code != 0
    # The error could be either from is_file() check or collect_file_stat()
    assert "is not a regular file" in _error_text(result)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="Unix sockets not available")
def test_socket_rejected(cli_runner, tmp_path, monkeypatch):
    """Test that Unix domain sockets are rejected."""
    monkeypatch.chdir(tmp_path)
    socket_path = tmp_path / "socket.md"

    # Create a Unix domain socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.bind(str(socket_path))
    except OSError as error:  # pragma: no cover - platform dependent
        pytest.skip(f"Unable to create socket: {error}")
    finally:
        sock.close()

    result = cli_runner.invoke(cli_module.cli, [str(socket_path)])
    assert result.exit_code != 0
    assert "is not a regular file" in _error_text(result)


def test_mocked_character_device_rejected(cli_runner, tmp_path, monkeypatch):
    """Test character device rejection using mocked stat to ensure CI coverage."""
    monkeypatch.chdir(tmp_path)
    device_path = tmp_path / "device.md"
    device_path.write_text("# Content\n", encoding="utf-8")

    # Mock os.stat to return character device mode
    original_stat = os.stat

    def mock_stat(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if str(path) == str(device_path):
            # Create a mock stat_result with S_IFCHR bit set
            class MockStatResult:
                st_mode = stat.S_IFCHR | 0o666
                st_size = result.st_size
                st_mtime = result.st_mtime
                st_mtime_ns = result.st_mtime_ns
                st_atime = result.st_atime
                st_atime_ns = result.st_atime_ns
                st_uid = result.st_uid if hasattr(result, "st_uid") else 0
                st_gid = result.st_gid if hasattr(result, "st_gid") else 0
                st_ino = result.st_ino if hasattr(result, "st_ino") else 0
                st_dev = result.st_dev if hasattr(result, "st_dev") else 0

            return MockStatResult()
        return result

    monkeypatch.setattr(os, "stat", mock_stat)

    result = cli_runner.invoke(cli_module.cli, [str(device_path)])
    assert result.exit_code != 0
    assert "is not a regular file" in _error_text(result)


def test_mocked_block_device_rejected(cli_runner, tmp_path, monkeypatch):
    """Test block device rejection using mocked stat to ensure CI coverage."""
    monkeypatch.chdir(tmp_path)
    device_path = tmp_path / "block.md"
    device_path.write_text("# Content\n", encoding="utf-8")

    # Mock os.stat to return block device mode
    original_stat = os.stat

    def mock_stat(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if str(path) == str(device_path):
            # Create a mock stat_result with S_IFBLK bit set
            class MockStatResult:
                st_mode = stat.S_IFBLK | 0o666
                st_size = result.st_size
                st_mtime = result.st_mtime
                st_mtime_ns = result.st_mtime_ns
                st_atime = result.st_atime
                st_atime_ns = result.st_atime_ns
                st_uid = result.st_uid if hasattr(result, "st_uid") else 0
                st_gid = result.st_gid if hasattr(result, "st_gid") else 0
                st_ino = result.st_ino if hasattr(result, "st_ino") else 0
                st_dev = result.st_dev if hasattr(result, "st_dev") else 0

            return MockStatResult()
        return result

    monkeypatch.setattr(os, "stat", mock_stat)

    result = cli_runner.invoke(cli_module.cli, [str(device_path)])
    assert result.exit_code != 0
    assert "is not a regular file" in _error_text(result)
