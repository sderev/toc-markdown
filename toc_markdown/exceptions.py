"""Package-specific exception types."""

from __future__ import annotations


class ParseError(ValueError):
    """Base class for parsing-related errors."""


class LineTooLongError(ParseError):
    """Raised when a line exceeds the configured maximum length."""

    def __init__(self, line_number: int, max_line_length: int):
        self.line_number = line_number
        self.max_line_length = max_line_length
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        return (
            f"Line {self.line_number} exceeds maximum allowed length "
            f"of {self.max_line_length} characters"
        )


class TooManyHeadersError(ParseError):
    """Raised when a document contains more headers than allowed."""

    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(f"Too many headers (limit: {self.limit})")
