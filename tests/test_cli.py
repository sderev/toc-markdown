from __future__ import annotations

import textwrap
from pathlib import Path

import toc_markdown.cli as cli_module
from toc_markdown.cli import cli
from toc_markdown.constants import MAX_TOC_SECTION_LINES, TOC_END_MARKER, TOC_START_MARKER


def _write(tmp_path: Path, filename: str, content: str) -> Path:
    path = tmp_path / filename
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return path


def _write_pyproject(base: Path, body: str) -> Path:
    path = base / "pyproject.toml"
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
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


def test_cli_updates_existing_toc_when_header_text_changes(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "update-header.md",
        f"""
        {TOC_START_MARKER}
        ## Table of Contents

        1. Old entry
        {TOC_END_MARKER}

        ## Section
        """,
    )

    result = cli_runner.invoke(cli, ["--header-text", "## Contents", str(target)])

    assert result.exit_code == 0
    contents = target.read_text(encoding="utf-8")
    assert "## Contents" in contents
    assert "## Table of Contents" not in contents
    assert "1. [Section](#section)" in contents
    assert "[Table of Contents](#table-of-contents)" not in contents


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


def test_cli_reads_config_from_pyproject(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        start_marker = "<!-- CUSTOM -->"
        end_marker = "<!-- /CUSTOM -->"
        header_text = "# Contents"
        min_level = 1
        indent_chars = ">>"
        list_style = "*"
        """,
    )
    target = _write(
        tmp_path,
        "configured.md",
        """
        # Top
        ## Inner
        """,
    )

    result = cli_runner.invoke(cli, [str(target)])

    assert result.exit_code == 0
    assert result.output.startswith("<!-- CUSTOM -->\n")
    assert "# Contents" in result.output
    assert ">>* [Inner](#inner)\n" in result.output


def test_cli_flags_override_config(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        start_marker = "<!-- CONFIG -->"
        end_marker = "<!-- /CONFIG -->"
        header_text = "# Config TOC"
        min_level = 3
        indent_chars = "    "
        list_style = "*"
        """,
    )
    target = _write(
        tmp_path,
        "override.md",
        """
        ## Heading
        ### Child
        """,
    )

    result = cli_runner.invoke(
        cli,
        [
            "--start-marker",
            "<!-- CLI -->",
            "--end-marker",
            "<!-- /CLI -->",
            "--header-text",
            "# CLI TOC",
            "--min-level",
            "2",
            "--list-style",
            "-",
            "--indent-chars",
            "\t",
            str(target),
        ],
    )

    assert result.exit_code == 0
    assert result.output.startswith("<!-- CLI -->\n")
    assert result.output.splitlines()[1] == "# CLI TOC"
    assert "- [Heading](#heading)\n" in result.output
    assert "\t- [Child](#child)\n" in result.output
    assert result.output.rstrip().endswith("<!-- /CLI -->")


def test_cli_accepts_unordered_list_style(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "alias.md",
        """
        ## Heading
        """,
    )

    result = cli_runner.invoke(cli, ["--list-style", "unordered", str(target)])

    assert result.exit_code == 0
    assert "- [Heading](#heading)\n" in result.output


def test_cli_preserve_unicode_flag(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = _write(
        tmp_path,
        "unicode.md",
        """
        ## Café
        """,
    )

    result = cli_runner.invoke(cli, ["--preserve-unicode", str(target)])

    assert result.exit_code == 0
    assert "[Café](#café)" in result.output
    assert "#cafe" not in result.output


def test_cli_respects_configured_preserve_unicode(cli_runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        preserve_unicode = true
        """,
    )
    target = _write(
        tmp_path,
        "unicode-config.md",
        """
        ## Café
        """,
    )

    result = cli_runner.invoke(cli, [str(target)])

    assert result.exit_code == 0
    assert "[Café](#café)" in result.output
    assert "#cafe" not in result.output


def test_cli_public_api_excludes_header_pattern():
    assert "HEADER_PATTERN" not in cli_module.__all__
