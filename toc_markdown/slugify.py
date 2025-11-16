"""Slug generation for markdown headers."""

from __future__ import annotations

import re
import string
import unicodedata


def generate_slug(title: str) -> str:
    """
    Generates a slug for a given title to be used as an anchor link in markdown.

    Args:
        title (str): The title to generate a slug for.

    Returns:
        str: The generated slug.
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
