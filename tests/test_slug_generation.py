from __future__ import annotations

import pytest

from toc_markdown.slugify import generate_slug


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Hello World", "hello-world"),
        ("What's New?", "whats-new"),
        ("Café", "cafe"),
        ("", "untitled"),
        ("Multiple   Spaces", "multiple-spaces"),
    ],
)
def test_generate_slug_expected_examples(title: str, expected: str):
    """Validates slug generation for representative examples."""
    assert generate_slug(title) == expected


def test_generate_slug_handles_emojis_and_special_characters():
    slug = generate_slug("Read 📖, Write ✍️, Repeat!")
    assert slug == "read-write-repeat"


def test_generate_slug_returns_untitled_for_whitespace_only():
    assert generate_slug("   \n\t ") == "untitled"


def test_generate_slug_preserves_unicode_when_requested():
    assert generate_slug("Café", preserve_unicode=True) == "café"
    assert (
        generate_slug("Read 📖, Write ✍️, Repeat!", preserve_unicode=True)
        == "read-📖-write-✍️-repeat"
    )
