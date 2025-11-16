"""Table of contents generation for markdown files."""

from __future__ import annotations

from .constants import MAX_TOC_SECTION_LINES, TOC_END_MARKER, TOC_START_MARKER
from .parser import strip_markdown_links
from .slugify import generate_slug


def generate_toc_entries(headers: list[str]) -> list[str]:
    """
    Generates a table of contents from a list of headers.

    Handles duplicate headers using GitHub's convention: first occurrence gets
    the base slug, subsequent duplicates get numbered suffixes (-1, -2, etc.).
    Uses a hybrid approach with O(n) complexity for optimal performance while
    correctly handling cascading collisions.

    Args:
        headers (list): A list of markdown headers.

    Returns:
        list: A list of lines that make up the TOC.
    """
    toc = [f"{TOC_START_MARKER}\n", "## Table of Contents\n\n"]

    # Hybrid approach for duplicate slug handling:
    # - slug_counters: O(1) lookup for the next available counter for each base slug
    # - used_slugs: Validates actual slug availability to handle cascading collisions
    #
    # This dual-structure approach achieves O(n) complexity for the common case
    # (headers with unique titles or simple duplicates) while correctly handling
    # edge cases like cascading collisions where a numbered header's base slug
    # collides with an auto-numbered duplicate.
    #
    # Example of cascading collision that requires both structures:
    #   1. "Header" generates slug "header"
    #   2. "Header" (duplicate) generates slug "header-1"
    #   3. "Header 1" has base slug "header-1" which collides with #2
    #      The counter says next is "header-1-1" but we must verify it's not taken
    slug_counters: dict[str, int] = {}  # Track next counter for each base slug
    used_slugs: set[str] = set()        # Track all slugs actually in use

    for heading in headers:
        # Count only leading # characters, not all # in the string (e.g., URLs with #anchor)
        level = len(heading) - len(heading.lstrip("#"))
        title = heading[level:].strip()
        title = strip_markdown_links(title)
        base_slug = generate_slug(title)

        # Get the next counter for this base slug (GitHub convention: starts at 1)
        # First occurrence gets no suffix (count=0), then -1, -2, etc.
        count = slug_counters.get(base_slug, 0)
        link = base_slug if count == 0 else f"{base_slug}-{count}"

        # Handle cascading collisions: a slug might already be taken by a different
        # header whose base slug happens to match our generated slug with counter.
        # This is rare but must be handled correctly for edge cases like:
        # "Header", "Header", "Header 1" where "Header 1" -> "header-1" collides
        while link in used_slugs:
            count += 1
            link = f"{base_slug}-{count}"

        # Update tracking structures:
        # - Increment counter for next duplicate of this base slug
        # - Mark the actual slug as used
        slug_counters[base_slug] = count + 1
        used_slugs.add(link)

        toc.append("    " * (level - 2) + f"1. [{title}](#{link})" + "\n")

    toc.append(f"{TOC_END_MARKER}" + "\n")

    return toc


def validate_toc_markers(toc_start_line: int, toc_end_line: int) -> None:
    """Ensure TOC markers are sane before mutating the file."""

    if toc_start_line >= toc_end_line:
        raise ValueError(
            "Invalid TOC markers:\n"
            f"  Start marker at line {toc_start_line + 1}\n"
            f"  End marker at line {toc_end_line + 1}\n"
            "Start marker must come before end marker."
        )

    toc_size = toc_end_line - toc_start_line
    if toc_size > MAX_TOC_SECTION_LINES:
        raise ValueError(f"TOC section is suspiciously large ({toc_size} lines)")
