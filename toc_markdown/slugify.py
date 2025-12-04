"""Slug generation for markdown headers."""

from __future__ import annotations

import re
import string
import unicodedata


def generate_slug(title: str) -> str:
    """Generate a URL-style slug from a Markdown header title.

    Converts the title to lowercase ASCII, removes punctuation except hyphens
    and underscores, collapses whitespace to single hyphens, and returns
    ``"untitled"`` when no characters remain after normalization.

    Args:
        title: The header text to convert into a slug.

    Returns:
        str: Hyphen-separated slug suitable for anchor links. Returns
            ``"untitled"`` when the processed title is empty.

    Examples:
        generate_slug("Hello World")  # "hello-world"
        generate_slug("What's New?")  # "whats-new"
        generate_slug("   ")  # "untitled"
    """
    # Keep hyphens and underscores in the slug, but remove other punctuation
    punctuation = string.punctuation.replace("-", "").replace("_", "")

    # Step 1: Normalize unicode and convert to ASCII
    slug = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("utf-8", "ignore")

    # Step 2: Lowercase and remove punctuation (once)
    slug = slug.casefold()
    slug = slug.translate(str.maketrans("", "", punctuation))

    # Step 3: Handle whitespace and cleanup
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")

    return slug if slug else "untitled"
