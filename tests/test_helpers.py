from __future__ import annotations

import os
from pathlib import Path

import click
import pytest

from toc_markdown.cli import (
    collect_file_stat,
    contains_symlink,
    get_max_file_size,
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


def test_safe_read_raises_for_directory(tmp_path: Path):
    directory = tmp_path / "folder"
    directory.mkdir()

    with pytest.raises(IOError):
        safe_read(directory)
