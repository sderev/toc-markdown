from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from toc_markdown.config import TocConfig
from toc_markdown.constants import (
    CODE_FENCE,
    DEFAULT_MAX_LINE_LENGTH,
    TOC_END_MARKER,
    TOC_START_MARKER,
)
from toc_markdown.parser import ParseFileError, parse_file, parse_markdown


def _write_markdown(tmp_path: Path, content: str) -> Path:
    target = tmp_path / "sample.md"
    target.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return target


def test_parse_file_rejects_non_positive_override(tmp_path: Path):
    target = _write_markdown(tmp_path, "## Heading\n")
    with pytest.raises(ParseFileError):
        parse_file(target, 0)


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


def test_parse_file_ignores_existing_toc_header_when_header_text_changes(tmp_path: Path):
    target = _write_markdown(
        tmp_path,
        f"""
        {TOC_START_MARKER}
        ## Table of Contents

        1. [Section](#section)
        {TOC_END_MARKER}

        ## Section
        """,
    )
    config = TocConfig(header_text="## Contents")

    _, headers, _, _ = parse_file(target, DEFAULT_MAX_LINE_LENGTH, config)
    assert headers == ["## Section"]


def test_parse_file_handles_empty_file(tmp_path: Path):
    target = tmp_path / "empty.md"
    target.write_text("", encoding="utf-8")

    full_file, headers, toc_start, toc_end = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert full_file == []
    assert headers == []
    assert toc_start is None
    assert toc_end is None


def test_toc_markers_in_fenced_code_block_ignored(tmp_path: Path):
    """TOC markers inside fenced code blocks should not be detected."""
    target = _write_markdown(
        tmp_path,
        f"""
        ## Heading 1
        {CODE_FENCE}
        {TOC_START_MARKER}
        Fake TOC content
        {TOC_END_MARKER}
        {CODE_FENCE}
        ## Heading 2
        """,
    )

    _, headers, toc_start, toc_end = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert headers == ["## Heading 1", "## Heading 2"]
    assert toc_start is None
    assert toc_end is None


def test_mixed_real_and_fake_toc_markers(tmp_path: Path):
    """Real TOC outside code blocks, fake TOC inside should only detect real one."""
    target = _write_markdown(
        tmp_path,
        f"""
        {TOC_START_MARKER}
        Real TOC
        {TOC_END_MARKER}
        ## Heading 1
        {CODE_FENCE}
        {TOC_START_MARKER}
        Fake TOC
        {TOC_END_MARKER}
        {CODE_FENCE}
        ## Heading 2
        """,
    )

    _, headers, toc_start, toc_end = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert headers == ["## Heading 1", "## Heading 2"]
    # Only the real TOC should be detected
    assert toc_start == 0
    assert toc_end == 2


def test_toc_markers_in_indented_code_block_ignored(tmp_path: Path):
    target = _write_markdown(
        tmp_path,
        f"""
        ## Heading 1
            code line
            {TOC_START_MARKER}
            fake toc
            {TOC_END_MARKER}
        ## Heading 2
        """,
    )

    _, headers, toc_start, toc_end = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert headers == ["## Heading 1", "## Heading 2"]
    assert toc_start is None
    assert toc_end is None


def test_headers_inside_toc_not_parsed(tmp_path: Path):
    target = _write_markdown(
        tmp_path,
        f"""
        ## Before
        {TOC_START_MARKER}
        ## Inside TOC
        {TOC_END_MARKER}
        ### After
        """,
    )

    _, headers, toc_start, toc_end = parse_file(target, DEFAULT_MAX_LINE_LENGTH)
    assert headers == ["## Before", "### After"]
    assert toc_start == 1
    assert toc_end == 3


def test_toc_markers_mixed_with_indented_and_fenced_code(tmp_path: Path):
    content = "\n".join(
        [
            "## Heading 1",
            "    code line",
            "    <!-- TOC -->",
            "    code toc content",
            "    <!-- /TOC -->",
            "```",
            "<!-- TOC -->",
            "## fenced toc heading",
            "<!-- /TOC -->",
            "```",
            "<!-- TOC -->",
            "## Real TOC heading",
            "<!-- /TOC -->",
            "## Heading 2",
            "",
        ]
    )

    result = parse_markdown(content)

    assert result.headers == ["## Heading 1", "## Heading 2"]
    assert result.toc_start_line == 10
    assert result.toc_end_line == 12


def test_parse_markdown_cycles_fence_state_back_to_normal():
    content = "\n".join(
        [
            "```",
            "## Hidden",
            "```",
            "## Visible",
            "",
        ]
    )

    result = parse_markdown(content)

    assert result.headers == ["## Visible"]


def test_parse_markdown_transitions_from_indented_to_fenced_code():
    content = "\n".join(
        [
            "    code fence marker",
            "    still code",
            "```",
            "## Ignored in fenced code",
            "```",
            "## After blocks",
            "",
        ]
    )

    result = parse_markdown(content)

    assert result.headers == ["## After blocks"]


def test_parse_markdown_handles_unclosed_fence():
    content = "\n".join(
        [
            "```",
            "## Hidden",
            "## Still hidden",
            "",
        ]
    )

    result = parse_markdown(content)

    assert result.headers == []


def test_tab_indented_fence_treated_as_indented_code():
    content = "\n".join(
        [
            "\t```",
            "\t## Hidden",
            "\t```",
            "## Visible",
            "",
        ]
    )

    result = parse_markdown(content)

    assert result.headers == ["## Visible"]


def test_parse_markdown_rejects_overindented_closing_fence():
    content = "\n".join(
        [
            "   ```",
            "   inside",
            "      ```",
            "## Ignored because fence stays open",
            "",
        ]
    )

    result = parse_markdown(content)

    assert result.headers == []


def test_parse_markdown_respects_configured_levels():
    content = "\n".join(
        [
            "# Heading 1",
            "## Heading 2",
            "### Heading 3",
            "#### Heading 4",
            "##### Heading 5",
            "",
        ]
    )
    config = TocConfig(min_level=1, max_level=4)

    result = parse_markdown(content, config=config)

    assert result.headers == [
        "# Heading 1",
        "## Heading 2",
        "### Heading 3",
        "#### Heading 4",
    ]


def test_parse_markdown_handles_headers_with_multiple_spaces():
    """Headers with multiple spaces after # should be recognized (CommonMark compliant)."""
    content = "\n".join(
        [
            "##   Title with two spaces",
            "###    Title with three spaces",
            "## Normal single space",
            "",
        ]
    )

    result = parse_markdown(content)

    assert result.headers == [
        "##   Title with two spaces",
        "###    Title with three spaces",
        "## Normal single space",
    ]


def test_parse_markdown_handles_headers_with_tabs():
    """Headers with tabs after # should be recognized (CommonMark compliant)."""
    content = "##\tTitle with tab\n###\t\tTitle with two tabs\n## Normal\n"

    result = parse_markdown(content)

    assert result.headers == [
        "##\tTitle with tab",
        "###\t\tTitle with two tabs",
        "## Normal",
    ]


def test_parse_markdown_handles_headers_with_mixed_whitespace():
    """Headers with mixed spaces and tabs after # should be recognized."""
    content = "## \t Space then tab\n## \t \t Mixed whitespace\n"

    result = parse_markdown(content)

    assert result.headers == [
        "## \t Space then tab",
        "## \t \t Mixed whitespace",
    ]


def test_parse_markdown_allows_empty_headers():
    """Whitespace-only heading text after # is still a valid heading."""
    content = "##\n###\n##   \n###\t\t\n## Normal\n"

    result = parse_markdown(content)

    assert result.headers == ["##", "###", "##   ", "###\t\t", "## Normal"]


def test_parse_markdown_requires_whitespace_after_hashes():
    """Headings must have at least one space or tab after the hashes."""
    content = "##NoSpace\n## Valid\n"

    result = parse_markdown(content)

    assert result.headers == ["## Valid"]
