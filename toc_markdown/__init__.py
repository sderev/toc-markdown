"""
toc-markdown: Table of Contents generator for Markdown files.

This package can be used both as a CLI tool and as a library.

CLI Usage:
    toc-markdown README.md

Library Usage:
    from pathlib import Path
    from toc_markdown import parse_markdown, generate_toc_entries

    content = Path("README.md").read_text()
    result = parse_markdown(content)
    toc_lines = generate_toc_entries(result.headers)
    toc_text = "".join(toc_lines)
"""

from .exceptions import LineTooLongError, ParseError, TooManyHeadersError
from .generator import generate_toc_entries, validate_toc_markers
from .models import ParseResult
from .parser import parse_markdown, strip_markdown_links
from .slugify import generate_slug

__version__ = "0.0.2"

__all__ = [
    # Core functionality
    "parse_markdown",
    "generate_toc_entries",
    "generate_slug",
    "strip_markdown_links",
    # Data models
    "ParseResult",
    # Utilities
    "validate_toc_markers",
    # Exceptions
    "LineTooLongError",
    "ParseError",
    "TooManyHeadersError",
    # Version
    "__version__",
]
