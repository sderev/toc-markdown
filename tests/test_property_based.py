from __future__ import annotations

import string

from hypothesis import given
from hypothesis import strategies as st
from toc_markdown.cli import generate_slug, generate_toc


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
