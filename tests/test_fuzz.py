from __future__ import annotations

import os

import pytest
from toc_markdown.cli import TOC_END_MARKER, TOC_START_MARKER, generate_slug, generate_toc

atheris = pytest.importorskip("atheris")


def test_generate_slug_with_fuzzed_input():
    data = os.urandom(4096)
    provider = atheris.FuzzedDataProvider(data)
    generated = set()

    for _ in range(128):
        if provider.remaining_bytes() == 0:
            break
        text = provider.ConsumeUnicodeNoSurrogates(64)
        slug = generate_slug(text)
        slug.encode("ascii")
        assert slug == slug.casefold()
        generated.add(slug)

    assert generated  # ensure we exercised the loop


def test_generate_toc_with_fuzzed_headers():
    data = os.urandom(4096)
    provider = atheris.FuzzedDataProvider(data)
    headers: list[str] = []

    while provider.remaining_bytes() > 0 and len(headers) < 32:
        level = 2 if provider.ConsumeBool() else 3
        title = provider.ConsumeUnicodeNoSurrogates(32) or "Section"
        headers.append(f"{'#' * level} {title}")

    toc = generate_toc(headers)
    assert toc[0] == f"{TOC_START_MARKER}\n"
    assert toc[-1] == f"{TOC_END_MARKER}\n"
