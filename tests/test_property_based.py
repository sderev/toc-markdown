from __future__ import annotations

import string

from hypothesis import assume, given
from hypothesis import strategies as st
from toc_markdown.cli import generate_slug, generate_toc
from toc_markdown.constants import CLOSING_FENCE_MAX_INDENT
from toc_markdown.models import ParserContext, ParserState
from toc_markdown.parser import (
    _try_close_fence,
    _try_exit_indented_code,
    _try_open_fence,
    parse_markdown,
)


@given(st.text())
def test_generate_slug_is_ascii_lowercase_and_non_empty(title: str):
    slug = generate_slug(title)
    assert slug  # never empty
    assert slug == slug.casefold()
    slug.encode("ascii")
    assert " " not in slug


@given(st.text(alphabet=" \t\n", min_size=0))
def test_blank_titles_always_return_untitled(title: str):
    assert generate_slug(title) == "untitled"


@given(st.text())
def test_generate_slug_is_idempotent(title: str):
    slug = generate_slug(title)
    assert generate_slug(slug) == slug


title_strategy = st.text(
    alphabet=string.ascii_letters + string.digits + " _-",
    min_size=1,
    max_size=32,
)


@given(
    st.lists(
        st.tuples(st.integers(min_value=2, max_value=4), title_strategy), min_size=1, max_size=20
    )
)
def test_all_generated_slugs_are_unique(data):
    """Property: All slugs in a TOC must be unique, even with duplicate headers."""
    import re

    headers = [f"{'#' * level} {title}" for level, title in data]
    toc = generate_toc(headers)

    # Extract all slugs from TOC entries using regex
    slug_pattern = re.compile(r"\]\(#([^)]+)\)")
    slugs = []
    for line in toc:
        match = slug_pattern.search(line)
        if match:
            slugs.append(match.group(1))

    # Assert all slugs are unique
    assert len(slugs) == len(set(slugs)), f"Found duplicate slugs: {slugs}"


@given(
    st.lists(
        st.tuples(st.integers(min_value=2, max_value=3), title_strategy), min_size=1, max_size=10
    )
)
def test_toc_generation_is_deterministic(data):
    """Property: Same input should always produce same output."""
    headers = [f"{'#' * level} {title}" for level, title in data]

    toc1 = generate_toc(headers)
    toc2 = generate_toc(headers)

    assert toc1 == toc2


@given(st.text(max_size=200))
def test_parse_markdown_is_deterministic(content: str):
    result_one = parse_markdown(content)
    result_two = parse_markdown(content)

    assert result_one == result_two


@given(
    st.integers(min_value=0, max_value=3),
    st.sampled_from(["`", "~"]),
    st.integers(min_value=3, max_value=10),
    st.integers(min_value=0, max_value=3),
)
def test_parser_context_resets_after_fence_cycle(
    indent_columns: int, fence_char: str, fence_length: int, additional_indent: int
):
    ctx = ParserContext()

    open_line = f"{' ' * indent_columns}{fence_char * fence_length}"
    close_line = f"{' ' * (indent_columns + additional_indent)}{fence_char * (fence_length + 1)}"
    assume(indent_columns + additional_indent <= CLOSING_FENCE_MAX_INDENT)

    assert _try_open_fence(ctx, open_line) is True
    assert ctx.state is ParserState.IN_FENCED_CODE

    assert _try_close_fence(ctx, close_line) is True
    assert ctx.state is ParserState.NORMAL
    assert ctx.fence_char is None
    assert ctx.fence_length == 0
    assert ctx.fence_indent_columns == 0


@given(
    st.integers(min_value=0, max_value=3),
    st.text(alphabet=string.ascii_letters, min_size=1, max_size=20),
)
def test_indented_code_exits_on_dedent(indent_columns: int, content: str):
    ctx = ParserContext(state=ParserState.IN_INDENTED_CODE)
    line = f"{' ' * indent_columns}{content}"

    assert _try_exit_indented_code(ctx, line) is False
    assert ctx.state is ParserState.NORMAL
