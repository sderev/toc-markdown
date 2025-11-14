from __future__ import annotations

import os
import socket
import stat
from pathlib import Path

import click
import pytest

from toc_markdown.cli import (
    collect_file_stat,
    contains_symlink,
    get_max_file_size,
    get_max_line_length,
    normalize_filepath,
    safe_read,
)


def test_get_max_file_size_rejects_non_integer(monkeypatch):
    monkeypatch.setenv("TOC_MARKDOWN_MAX_FILE_SIZE", "invalid")
    with pytest.raises(click.ClickException):
        get_max_file_size()


def test_get_max_file_size_rejects_non_positive(monkeypatch):
    monkeypatch.setenv("TOC_MARKDOWN_MAX_FILE_SIZE", "0")
    with pytest.raises(click.ClickException):
        get_max_file_size()


def test_get_max_line_length_rejects_non_integer(monkeypatch):
    monkeypatch.setenv("TOC_MARKDOWN_MAX_LINE_LENGTH", "invalid")
    with pytest.raises(click.ClickException):
        get_max_line_length()


def test_get_max_line_length_rejects_non_positive(monkeypatch):
    monkeypatch.setenv("TOC_MARKDOWN_MAX_LINE_LENGTH", "0")
    with pytest.raises(click.ClickException):
        get_max_line_length()


def test_normalize_filepath_missing_file(tmp_path: Path):
    with pytest.raises(click.BadParameter):
        normalize_filepath(str(tmp_path / "missing.md"), tmp_path)


def test_normalize_filepath_handles_oserror(monkeypatch, tmp_path: Path):
    target = tmp_path / "doc.md"
    target.write_text("## Heading\n", encoding="utf-8")
    base_dir = tmp_path
    original_resolve = Path.resolve

    def _raise_oserror(self, strict=True):
        if self == target:
            raise OSError("resolve boom")
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", _raise_oserror)
    with pytest.raises(click.BadParameter):
        normalize_filepath(str(target), base_dir)


def test_normalize_filepath_rejects_directory(tmp_path: Path):
    folder = tmp_path / "folder"
    folder.mkdir()
    with pytest.raises(click.BadParameter):
        normalize_filepath(str(folder), tmp_path)


def test_contains_symlink_handles_oserror(monkeypatch, tmp_path: Path):
    probe = tmp_path / "probe.md"
    probe.write_text("## Heading\n", encoding="utf-8")
    original_is_symlink = Path.is_symlink
    call_count = {"count": 0}

    def _flaky_is_symlink(self):
        if self == probe and call_count["count"] == 0:
            call_count["count"] += 1
            raise OSError("stat boom")
        return original_is_symlink(self)

    monkeypatch.setattr(Path, "is_symlink", _flaky_is_symlink)
    assert contains_symlink(probe) is False


def test_collect_file_stat_handles_missing_file(tmp_path: Path):
    with pytest.raises(IOError):
        collect_file_stat(tmp_path / "missing.md")


def test_collect_file_stat_rejects_symlink(tmp_path: Path):
    target = tmp_path / "actual.md"
    target.write_text("## Heading\n", encoding="utf-8")
    link = tmp_path / "alias.md"
    os.symlink(target, link)

    with pytest.raises(IOError):
        collect_file_stat(link)


def test_collect_file_stat_rejects_directory(tmp_path: Path):
    directory = tmp_path / "folder"
    directory.mkdir()
    with pytest.raises(IOError):
        collect_file_stat(directory)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="mkfifo not available")
def test_collect_file_stat_rejects_fifo(tmp_path: Path):
    """Test that FIFOs are rejected at the collect_file_stat level."""
    fifo = tmp_path / "pipe.md"
    try:
        os.mkfifo(fifo)
    except OSError:  # pragma: no cover
        pytest.skip("Unable to create FIFO")

    with pytest.raises(IOError) as exc_info:
        collect_file_stat(fifo)
    assert "is not a regular file" in str(exc_info.value)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="Unix sockets not available")
def test_collect_file_stat_rejects_socket(tmp_path: Path):
    """Test that Unix sockets are rejected at the collect_file_stat level."""
    socket_path = tmp_path / "socket.md"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.bind(str(socket_path))
    except OSError:  # pragma: no cover
        pytest.skip("Unable to create socket")
    finally:
        sock.close()

    with pytest.raises(IOError) as exc_info:
        collect_file_stat(socket_path)
    assert "is not a regular file" in str(exc_info.value)


def test_collect_file_stat_rejects_mocked_character_device(tmp_path: Path, monkeypatch):
    """Test that character devices are rejected using mocked stat."""
    device = tmp_path / "device.md"
    device.write_text("# Content\n", encoding="utf-8")

    # Mock os.stat to return character device mode
    original_stat = os.stat
    def mock_stat(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if str(path) == str(device):
            # Create a mock stat_result with S_IFCHR bit set
            class MockStatResult:
                st_mode = stat.S_IFCHR | 0o666
                st_size = result.st_size
                st_mtime = result.st_mtime
                st_mtime_ns = result.st_mtime_ns
                st_atime = result.st_atime
                st_atime_ns = result.st_atime_ns
                st_uid = result.st_uid if hasattr(result, 'st_uid') else 0
                st_gid = result.st_gid if hasattr(result, 'st_gid') else 0
                st_ino = result.st_ino if hasattr(result, 'st_ino') else 0
                st_dev = result.st_dev if hasattr(result, 'st_dev') else 0
            return MockStatResult()
        return result

    monkeypatch.setattr(os, "stat", mock_stat)

    with pytest.raises(IOError) as exc_info:
        collect_file_stat(device)
    assert "is not a regular file" in str(exc_info.value)


def test_collect_file_stat_rejects_mocked_block_device(tmp_path: Path, monkeypatch):
    """Test that block devices are rejected using mocked stat."""
    device = tmp_path / "block.md"
    device.write_text("# Content\n", encoding="utf-8")

    # Mock os.stat to return block device mode
    original_stat = os.stat
    def mock_stat(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if str(path) == str(device):
            # Create a mock stat_result with S_IFBLK bit set
            class MockStatResult:
                st_mode = stat.S_IFBLK | 0o666
                st_size = result.st_size
                st_mtime = result.st_mtime
                st_mtime_ns = result.st_mtime_ns
                st_atime = result.st_atime
                st_atime_ns = result.st_atime_ns
                st_uid = result.st_uid if hasattr(result, 'st_uid') else 0
                st_gid = result.st_gid if hasattr(result, 'st_gid') else 0
                st_ino = result.st_ino if hasattr(result, 'st_ino') else 0
                st_dev = result.st_dev if hasattr(result, 'st_dev') else 0
            return MockStatResult()
        return result

    monkeypatch.setattr(os, "stat", mock_stat)

    with pytest.raises(IOError) as exc_info:
        collect_file_stat(device)
    assert "is not a regular file" in str(exc_info.value)


def test_safe_read_raises_for_directory(tmp_path: Path):
    directory = tmp_path / "folder"
    directory.mkdir()

    with pytest.raises(IOError):
        safe_read(directory)
