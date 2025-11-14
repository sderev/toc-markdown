from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from toc_markdown.cli import (
    CODE_FENCE,
    DEFAULT_MAX_LINE_LENGTH,
    TOC_END_MARKER,
    TOC_START_MARKER,
    parse_file,
)


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

    _, headers, _, _ = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
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

    _, headers, _, _ = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert headers == ["## Visible", "### Still Visible"]


def test_parse_file_handles_tilde_fences_with_info_strings(tmp_path: Path):
    target = _write_markdown(
        tmp_path,
        """
        ## Visible
           ~~~python
           ## Hidden
             ~~~
        ### After
        """,
    )

    _, headers, _, _ = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert headers == ["## Visible", "### After"]


def test_parse_file_does_not_close_fences_with_deep_indentation(tmp_path: Path):
    target = _write_markdown(
        tmp_path,
        "\n".join(
            [
                "```",
                "    ```",
                "    ## Hidden",
                "    ```",
                "```",
                "## After",
            ]
        )
        + "\n",
    )

    _, headers, _, _ = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert headers == ["## After"]


def test_parse_file_ignores_short_fence_sequences(tmp_path: Path):
    target = _write_markdown(
        tmp_path,
        "\n".join(
            [
                "```",
                "``",
                "## Hidden",
                "```",
                "## After",
            ]
        )
        + "\n",
    )

    _, headers, _, _ = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert headers == ["## After"]


@pytest.mark.parametrize("prefix", [" \t", "  \t", "   \t", " \t "])
def test_parse_file_counts_mixed_whitespace_indents(tmp_path: Path, prefix: str):
    target = _write_markdown(
        tmp_path,
        "\n".join(
            [
                "## Visible",
                f"{prefix}## Hidden",
                "### After",
            ]
        )
        + "\n",
    )

    _, headers, _, _ = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert headers == ["## Visible", "### After"]


def test_parse_file_closes_fences_inside_lists(tmp_path: Path):
    target = _write_markdown(
        tmp_path,
        """
        - item
          ```
          ## Hidden
            ```
        ## After
        """,
    )

    _, headers, _, _ = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert headers == ["## After"]


def test_parse_file_ignores_indented_code_blocks(tmp_path: Path):
    target = _write_markdown(
        tmp_path,
        """
        ## Visible
            ## Hidden

        ### Another
        """,
    )

    _, headers, _, _ = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert headers == ["## Visible", "### Another"]


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

    _, headers, toc_start, toc_end = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert headers == ["## Heading"]
    assert toc_start == 0
    assert toc_end == 4


def test_parse_file_handles_empty_file(tmp_path: Path):
    target = tmp_path / "empty.md"
    target.write_text("", encoding="utf-8")

    full_file, headers, toc_start, toc_end = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert full_file == []
    assert headers == []
    assert toc_start is None
    assert toc_end is None
