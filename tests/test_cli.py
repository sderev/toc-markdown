from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from toc_markdown.cli import (
    MAX_TOC_SECTION_LINES,
    TOC_END_MARKER,
    TOC_START_MARKER,
    cli,
    parse_file,
)


def _write(tmp_path: Path, filename: str, content: str) -> Path:
    path = tmp_path / filename
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return path


def test_cli_prints_toc_when_missing(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "doc.md",
        """
        ## Introduction
        ### Basics
        """,
    )

    result = cli_runner.invoke(cli, [str(target)])
    assert result.exit_code == 0
    assert result.output.startswith(f"{TOC_START_MARKER}\n")
    assert target.read_text(encoding="utf-8").startswith("## Introduction")


def test_cli_updates_existing_toc(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "update.md",
        f"""
        {TOC_START_MARKER}
        ## Table of Contents

        1. Old entry
        {TOC_END_MARKER}
        ## Heading
        ### Details
        """,
    )

    result = cli_runner.invoke(cli, [str(target)])
    assert result.exit_code == 0
    contents = target.read_text(encoding="utf-8")
    assert "1. [Heading](#heading)" in contents
    assert "    1. [Details](#details)" in contents
    assert result.output == ""


def test_cli_rejects_non_markdown_files(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "notes.txt",
        """
        ## Heading
        """,
    )

    result = cli_runner.invoke(cli, [str(target)])
    assert result.exit_code != 0
    assert "not a Markdown file" in result.output


def test_cli_rejects_reversed_markers(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "reversed.md"
    target.write_text(
        "\n".join(
            [
                "Important content",
                TOC_END_MARKER,
                "Middle content that would be lost",
                TOC_START_MARKER,
                "## End",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, [str(target)])

    assert result.exit_code != 0
    assert "Start marker must come before end marker." in result.output


def test_cli_rejects_unreasonably_large_toc(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    filler_lines = ["line"] * (MAX_TOC_SECTION_LINES + 1)
    target = tmp_path / "huge.md"
    target.write_text(
        "\n".join(
            [
                TOC_START_MARKER,
                *filler_lines,
                TOC_END_MARKER,
                "## Heading",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, [str(target)])

    assert result.exit_code != 0
    assert "TOC section is suspiciously large" in result.output
