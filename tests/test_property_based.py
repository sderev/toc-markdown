from __future__ import annotations

import string

from hypothesis import given, strategies as st

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


@given(st.lists(st.tuples(st.integers(min_value=2, max_value=3), title_strategy), max_size=8))
def test_generate_toc_matches_slug_generation(data):
    headers = [f"{'#' * level} {title}" for level, title in data]
    toc = generate_toc(headers)

    for level, title in data:
        indent = "    " * (level - 2)
        clean_title = title.strip()
        slug = generate_slug(clean_title)
        entry = f"{indent}1. [{clean_title}](#{slug})\n"
        assert entry in toc
