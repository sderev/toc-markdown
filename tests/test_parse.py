from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from toc_markdown.cli import CODE_FENCE, TOC_END_MARKER, TOC_START_MARKER, parse_file


def _write_markdown(tmp_path: Path, content: str) -> Path:
    target = tmp_path / "sample.md"
    target.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return target


def test_parse_file_detects_only_h2_and_h3(tmp_path: Path):
    target = _write_markdown(
        tmp_path,
        """
        # Heading 1
        ## Heading 2
        ### Heading 3
        #### Heading 4
        """,
    )

    _, headers, _, _ = parse_file(target)
    assert headers == ["## Heading 2", "### Heading 3"]


def test_parse_file_ignores_code_blocks(tmp_path: Path):
    target = _write_markdown(
        tmp_path,
        f"""
        ## Visible
        {CODE_FENCE}
        ## Hidden
        {CODE_FENCE}
        ### Still Visible
        """,
    )

    _, headers, _, _ = parse_file(target)
    assert headers == ["## Visible", "### Still Visible"]


def test_parse_file_tracks_toc_markers(tmp_path: Path):
    target = _write_markdown(
        tmp_path,
        f"""
        {TOC_START_MARKER}
        ## Table of Contents

        1. Example
        {TOC_END_MARKER}
        ## Heading
        """,
    )

    _, headers, toc_start, toc_end = parse_file(target)
    assert headers == ["## Heading"]
    assert toc_start == 0
    assert toc_end == 4


def test_parse_file_handles_empty_file(tmp_path: Path):
    target = tmp_path / "empty.md"
    target.write_text("", encoding="utf-8")

    full_file, headers, toc_start, toc_end = parse_file(target)
    assert full_file == []
    assert headers == []
    assert toc_start is None
    assert toc_end is None
