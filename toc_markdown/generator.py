"""Table of contents generation for markdown files."""

from __future__ import annotations

from .config import TocConfig, normalize_config, validate_config
from .parser import strip_markdown_links
from .slugify import generate_slug


def generate_toc_entries(headers: list[str], config: TocConfig | None = None) -> list[str]:
    """Render table-of-contents lines from parsed headers.

    Deduplicates slugs using GitHub-style numbering, including cascading
    collisions (for example, ``"Header"``, ``"Header"``, ``"Header 1"`` yields
    ``header``, ``header-1``, ``header-1-1``). Adds configured markers and
    header text to the output.

    Args:
        headers: Markdown header lines, including leading ``#`` characters.
        config: Configuration for indentation, list style, and limits. Defaults
            to a new `TocConfig` when omitted.

    Returns:
        list[str]: Lines that compose the TOC, each ending with a newline.

    Raises:
        ConfigError: If the configuration fails validation.

    Examples:
        generate_toc_entries(["# Title", "## Details"], TocConfig(min_level=1))
        generate_toc_entries(["# Header", "# Header", "# Header 1"])
    """
    config = normalize_config(config or TocConfig())
    validate_config(config)

    toc = [f"{config.start_marker}\n", f"{config.header_text}\n\n"]

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
    used_slugs: set[str] = set()  # Track all slugs actually in use

    for heading in headers:
        # Count only leading # characters, not all # in the string (e.g., URLs with #anchor)
        level = len(heading) - len(heading.lstrip("#"))
        title = heading[level:].strip()
        title = strip_markdown_links(title)
        base_slug = generate_slug(title, preserve_unicode=config.preserve_unicode)

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

        indent = config.indent_chars * max(level - config.min_level, 0)
        toc.append(f"{indent}{config.list_style} [{title}](#{link})\n")

    toc.append(f"{config.end_marker}\n")

    return toc


def validate_toc_markers(
    toc_start_line: int, toc_end_line: int, config: TocConfig | None = None
) -> None:
    """Validate TOC marker positions before mutating the file.

    Args:
        toc_start_line: Zero-based index of the TOC start marker.
        toc_end_line: Zero-based index of the TOC end marker.
        config: Configuration used to derive the maximum allowable TOC span.

    Returns:
        None.

    Raises:
        ValueError: If the start marker is after the end marker or the computed
            TOC span is suspiciously large.
        ConfigError: If the configuration fails validation.

    Examples:
        validate_toc_markers(10, 25, TocConfig(max_headers=100))
    """

    config = config or TocConfig()
    validate_config(config)

    if toc_start_line >= toc_end_line:
        raise ValueError(
            "Invalid TOC markers:\n"
            f"  Start marker at line {toc_start_line + 1}\n"
            f"  End marker at line {toc_end_line + 1}\n"
            "Start marker must come before end marker."
        )

    toc_size = toc_end_line - toc_start_line
    max_toc_lines = config.max_headers + 100
    if toc_size > max_toc_lines:
        raise ValueError(f"TOC section is suspiciously large ({toc_size} lines)")
