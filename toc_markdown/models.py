"""Data models for toc-markdown."""

from dataclasses import dataclass


@dataclass
class ParseResult:
    """Result of parsing a Markdown file.

    Attributes:
        full_file: A list of lines in the file.
        headers: A list of headers found in the file.
        toc_start_line: The line number where the TOC starts, or None if not found.
        toc_end_line: The line number where the TOC ends, or None if not found.
    """

    full_file: list[str]
    headers: list[str]
    toc_start_line: int | None
    toc_end_line: int | None
