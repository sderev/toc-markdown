from __future__ import annotations

import os
import stat
import textwrap
import uuid
from pathlib import Path

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

    def _parse_and_mutate(path: Path):
        result = original_parse(path)
        existing = path.read_text(encoding="utf-8")
        path.write_text(existing + "\n## Mutated\n", encoding="utf-8")
        return result

    monkeypatch.setattr(cli_module, "parse_file", _parse_and_mutate)
    result = cli_runner.invoke(cli_module.cli, [str(target)])

    assert result.exit_code != 0
    assert "changed during processing" in str(result.exception)
