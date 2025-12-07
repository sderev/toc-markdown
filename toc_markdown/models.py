"""Data models for toc-markdown."""

from dataclasses import dataclass
from enum import Enum, auto


class ParserState(Enum):
    """Parser states used while scanning Markdown content.

    Distinguishes normal text, fenced code blocks, and indented code blocks.

    Attributes:
        NORMAL: Default state for regular text.
        IN_TOC: Inside a validated TOC region.
        IN_FENCED_CODE: Inside a fenced code block.
        IN_INDENTED_CODE: Inside an indented code block.
    """

    NORMAL = auto()
    IN_TOC = auto()
    IN_FENCED_CODE = auto()
    IN_INDENTED_CODE = auto()


@dataclass
class ParserContext:
    """Encapsulate parser state while walking Markdown text.

    Attributes:
        state: Current parser state.
        fence_char: Fence character that opened a fenced code block, if any.
        fence_length: Number of fence characters that opened the block.
        fence_indent_columns: Indentation width preceding the opening fence.
    """

    state: ParserState = ParserState.NORMAL
    fence_char: str | None = None
    fence_length: int = 0
    fence_indent_columns: int = 0


@dataclass
class ParseResult:
    """Structured result of parsing a Markdown file.

    Attributes:
        full_file: Lines from the file, including trailing newlines.
        headers: Headers discovered during parsing.
        toc_start_line: Zero-based index where the TOC starts, or None when absent.
        toc_end_line: Zero-based index where the TOC ends, or None when absent.
    """

    full_file: list[str]
    headers: list[str]
    toc_start_line: int | None
    toc_end_line: int | None
