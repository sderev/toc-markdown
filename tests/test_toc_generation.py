from __future__ import annotations

from toc_markdown.cli import TOC_END_MARKER, TOC_START_MARKER, generate_toc


def test_generate_toc_for_simple_headers():
    headers = ["## Features", "## Installation"]
    toc = generate_toc(headers)

    assert toc == [
        f"{TOC_START_MARKER}\n",
        "## Table of Contents\n\n",
        "1. [Features](#features)\n",
        "1. [Installation](#installation)\n",
        f"{TOC_END_MARKER}\n",
    ]


def test_generate_toc_preserves_hierarchy():
    headers = ["## Parent", "### Child", "### Details"]
    toc = generate_toc(headers)

    assert "1. [Parent](#parent)\n" in toc
    assert "    1. [Child](#child)\n" in toc
    assert "    1. [Details](#details)\n" in toc


def test_generate_toc_handles_special_characters():
    headers = ["## Café & Résumé", "### C++/CLI"]
    toc = generate_toc(headers)

    assert "1. [Café & Résumé](#cafe-resume)\n" in toc
    assert "    1. [C++/CLI](#ccli)\n" in toc


def test_generate_toc_empty_headers():
    toc = generate_toc([])
    assert toc == [
        f"{TOC_START_MARKER}\n",
        "## Table of Contents\n\n",
        f"{TOC_END_MARKER}\n",
    ]


def test_generate_toc_single_link_in_header():
    """Test that a header with a single link extracts only the link text."""
    headers = ["## [Link Text](https://example.com)"]
    toc = generate_toc(headers)

    assert "1. [Link Text](#link-text)\n" in toc


def test_generate_toc_link_with_surrounding_text():
    """Test header with link and surrounding text."""
    headers = ["## See [Documentation](url) for details"]
    toc = generate_toc(headers)

    assert "1. [See Documentation for details](#see-documentation-for-details)\n" in toc


def test_generate_toc_multiple_links_in_header():
    """Test header with multiple links."""
    headers = ["## [First](url1) and [Second](url2)"]
    toc = generate_toc(headers)

    assert "1. [First and Second](#first-and-second)\n" in toc


def test_generate_toc_nested_header_with_link():
    """Test nested header (###) with link."""
    headers = ["## Parent", "### [Child Link](url)"]
    toc = generate_toc(headers)

    assert "1. [Parent](#parent)\n" in toc
    assert "    1. [Child Link](#child-link)\n" in toc


def test_generate_toc_link_with_special_characters():
    """Test that special characters in link text are handled correctly in slug."""
    headers = ["## [Café & Résumé](url)"]
    toc = generate_toc(headers)

    assert "1. [Café & Résumé](#cafe-resume)\n" in toc


def test_generate_toc_mixed_headers_with_and_without_links():
    """Test mix of headers with and without links."""
    headers = [
        "## Regular Header",
        "## [Linked Header](url)",
        "### Normal Subheader",
        "### [Linked Subheader](url)",
    ]
    toc = generate_toc(headers)

    assert "1. [Regular Header](#regular-header)\n" in toc
    assert "1. [Linked Header](#linked-header)\n" in toc
    assert "    1. [Normal Subheader](#normal-subheader)\n" in toc
    assert "    1. [Linked Subheader](#linked-subheader)\n" in toc


def test_generate_toc_link_with_complex_url():
    """Test link with complex URL is stripped correctly."""
    headers = ["## [Title](https://example.com/path?param=value#anchor)"]
    toc = generate_toc(headers)

    assert "1. [Title](#title)\n" in toc


def test_generate_toc_brackets_without_link():
    """Test that brackets without link syntax are preserved."""
    headers = ["## Text with [brackets] only"]
    toc = generate_toc(headers)

    assert "1. [Text with [brackets] only](#text-with-brackets-only)\n" in toc


def test_generate_toc_empty_link_text():
    """Test header with empty link text."""
    headers = ["## [](url) Header"]
    toc = generate_toc(headers)

    assert "1. [ Header](#header)\n" in toc


def test_generate_toc_url_with_parentheses():
    """Test URLs with parentheses are handled correctly."""
    headers = ["## [Wikipedia](https://en.wikipedia.org/wiki/Bracket_(disambiguation))"]
    toc = generate_toc(headers)

    assert "1. [Wikipedia](#wikipedia)\n" in toc


def test_generate_toc_link_in_inline_code():
    """Test links inside inline code are preserved."""
    headers = ["## Use `[link](url)` syntax"]
    toc = generate_toc(headers)

    assert "1. [Use `[link](url)` syntax](#use-linkurl-syntax)\n" in toc


def test_generate_toc_double_backtick_inline_code():
    """Test links inside double-backtick inline code are preserved."""
    headers = ["## Use `` `[link](url)` `` syntax"]
    toc = generate_toc(headers)

    assert "1. [Use `` `[link](url)` `` syntax](#use-linkurl-syntax)\n" in toc


def test_generate_toc_triple_backtick_inline_code():
    """Test links inside triple-backtick inline code are preserved."""
    headers = ["## Use ``` ``[link](url)`` ``` syntax"]
    toc = generate_toc(headers)

    assert "1. [Use ``` ``[link](url)`` ``` syntax](#use-linkurl-syntax)\n" in toc


def test_generate_toc_deeply_nested_parentheses():
    """Test URLs with deeply nested parentheses (2+ levels)."""
    headers = ["## [Link](https://en.wikipedia.org/wiki/Foo(bar(baz)))"]
    toc = generate_toc(headers)

    assert "1. [Link](#link)\n" in toc


def test_generate_toc_triple_nested_parentheses():
    """Test URLs with triple-nested parentheses."""
    headers = ["## [Link](https://example.com/foo(bar(baz(qux))))"]
    toc = generate_toc(headers)

    assert "1. [Link](#link)\n" in toc


def test_generate_toc_multi_backtick_and_nested_parens():
    """Test combining multi-backtick code with nested parentheses in real links."""
    headers = [
        "## [Nested Paren Link](https://example.com/foo(bar(baz)))",
        "## Use `` `[example](url)` `` for code",
    ]
    toc = generate_toc(headers)

    assert "1. [Nested Paren Link](#nested-paren-link)\n" in toc
    assert "1. [Use `` `[example](url)` `` for code](#use-exampleurl-for-code)\n" in toc


def test_generate_toc_escaped_paren_in_url():
    """Test URLs with escaped parentheses."""
    headers = [r"## [Link](https://example.com/foo\)bar) extra"]
    toc = generate_toc(headers)

    assert "1. [Link extra](#link-extra)\n" in toc


def test_generate_toc_escaped_bracket_in_link_text():
    """Test link text containing escaped brackets."""
    headers = [r"## [Example [Label \]]](https://example.com)"]
    toc = generate_toc(headers)

    assert "1. [Example [Label \\]]](#example-label)\n" in toc


def test_generate_toc_escaped_opening_bracket():
    """Test that escaped opening brackets are preserved."""
    headers = [r"## Escaped \[Link](https://example.com)"]
    toc = generate_toc(headers)

    assert "1. [Escaped \\[Link](https://example.com)](#escaped-linkhttpsexamplecom)\n" in toc


def test_generate_toc_escaped_backtick():
    """Test that escaped backticks don't create code spans."""
    headers = [r"## Escaped \`[Link](url)\` text"]
    toc = generate_toc(headers)

    assert "1. [Escaped \\`Link\\` text](#escaped-link-text)\n" in toc


def test_generate_toc_inline_image():
    """Test that inline images have ! removed."""
    headers = ["## ![Logo](logo.png) Introduction"]
    toc = generate_toc(headers)

    assert "1. [Logo Introduction](#logo-introduction)\n" in toc


def test_generate_toc_escaped_image_marker():
    """Test that escaped image markers are preserved."""
    headers = [r"## \![Alt](logo.png) Configuration"]
    toc = generate_toc(headers)

    assert "1. [\\![Alt](logo.png) Configuration](#altlogopng-configuration)\n" in toc


def test_generate_toc_angle_bracketed_url():
    """Test headers with angle-bracketed URLs."""
    headers = ["## [Link](<foo(bar>)"]
    toc = generate_toc(headers)

    assert "1. [Link](#link)\n" in toc


def test_generate_toc_angle_bracketed_url_with_parens():
    """Test headers with angle-bracketed URLs containing balanced parens."""
    headers = ["## [Wikipedia](<https://en.wikipedia.org/wiki/Foo(bar)>) Article"]
    toc = generate_toc(headers)

    assert "1. [Wikipedia Article](#wikipedia-article)\n" in toc


def test_generate_toc_reference_style_link():
    """Test headers with reference-style links."""
    headers = ["## [Documentation][docs] Overview"]
    toc = generate_toc(headers)

    assert "1. [Documentation Overview](#documentation-overview)\n" in toc


def test_generate_toc_reference_style_image():
    """Test headers with reference-style images."""
    headers = ["## ![Badge][build] Status"]
    toc = generate_toc(headers)

    assert "1. [Badge Status](#badge-status)\n" in toc


def test_generate_toc_mixed_link_types():
    """Test mixing different link types in headers."""
    headers = [
        "## [Inline](url) Header",
        "### [Reference][ref] Subheader",
        "### [Angle](<url(paren)>) Subheader",
    ]
    toc = generate_toc(headers)

    assert "1. [Inline Header](#inline-header)\n" in toc
    assert "    1. [Reference Subheader](#reference-subheader)\n" in toc
    assert "    1. [Angle Subheader](#angle-subheader)\n" in toc
