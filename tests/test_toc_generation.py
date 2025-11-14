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
