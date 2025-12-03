"""Markdown parsing utilities."""

from __future__ import annotations

import re

from .config import TocConfig, validate_config
from .constants import CLOSING_FENCE_MAX_INDENT, CODE_FENCE_PATTERN
from .exceptions import LineTooLongError, TooManyHeadersError
from .models import ParseResult, ParserContext, ParserState


def is_escaped(text: str, pos: int) -> bool:
    """
    Check if a character at position pos is escaped by counting preceding backslashes.

    A character is escaped if it's preceded by an odd number of backslashes.

    Args:
        text (str): The text to check.
        pos (int): The position of the character to check.

    Returns:
        bool: True if the character is escaped, False otherwise.
    """
    if pos == 0:
        return False

    # Count consecutive backslashes before pos
    backslash_count = 0
    i = pos - 1
    while i >= 0 and text[i] == "\\":
        backslash_count += 1
        i -= 1

    # Odd number of backslashes means the character is escaped
    return backslash_count % 2 == 1


def find_inline_code_spans(text: str) -> list[tuple[int, int]]:
    """
    Find all inline code spans in text and return their (start, end) positions.

    Follows CommonMark spec: inline code spans are delimited by backtick strings
    of equal length. For example, `code`, ``code``, ```code```, etc.

    Args:
        text (str): The text to scan for inline code spans.

    Returns:
        list[tuple[int, int]]: List of (start, end) positions for each code span.
    """
    spans = []
    i = 0

    while i < len(text):
        if text[i] == "`" and not is_escaped(text, i):
            # Count opening backticks (non-escaped)
            start = i
            backtick_count = 0
            while i < len(text) and text[i] == "`":
                backtick_count += 1
                i += 1

            # Look for closing backticks of same length
            while i < len(text):
                if text[i] == "`" and not is_escaped(text, i):
                    # Count closing backticks (non-escaped)
                    close_count = 0
                    while i < len(text) and text[i] == "`":
                        close_count += 1
                        i += 1

                    if close_count == backtick_count:
                        # Found matching closing backticks
                        spans.append((start, i))
                        break
                    # Otherwise, these backticks are part of content, continue searching
                else:
                    i += 1
        else:
            i += 1

    return spans


def strip_markdown_links(text: str) -> str:
    r"""
    Strips markdown link syntax from text, extracting only the link text.

    Converts `[text](url)` to just `text`, while preserving links inside inline code.
    Handles:
    * Multi-backtick inline code (e.g., `` `code` ``)
    * URLs with nested parentheses (e.g., `https://example.com/foo(bar(baz))`)
    * Angle-bracketed URLs (e.g., `[text](<url(with)parens>)`)
    * Reference-style links (e.g., `[text][ref]` or `![image][ref]`)
    * Escaped image markers (e.g., `\![text](url)` preserved as-is)

    Args:
        text (str): The text potentially containing markdown links.

    Returns:
        str: The text with markdown link syntax removed.
    """
    # Find all inline code spans using state machine
    code_spans = find_inline_code_spans(text)

    # Preserve inline code by replacing with placeholders
    inline_code_texts = []
    offset = 0
    text_parts = []

    for start, end in code_spans:
        # Add text before code span
        text_parts.append(text[offset:start])
        # Add placeholder for code span
        inline_code_texts.append(text[start:end])
        text_parts.append(f"\x00CODE_{len(inline_code_texts) - 1}\x00")
        offset = end

    # Add remaining text
    text_parts.append(text[offset:])
    text_with_placeholders = "".join(text_parts)

    # Strip markdown links using state machine for balanced parentheses
    result = []
    i = 0

    while i < len(text_with_placeholders):
        # Look for '[' that starts a potential link or image
        if text_with_placeholders[i] == "[" and not is_escaped(text_with_placeholders, i):
            # Check if this is preceded by escaped !, which means the entire ![...](...) should be preserved
            if (
                i > 0
                and text_with_placeholders[i - 1] == "!"
                and is_escaped(text_with_placeholders, i - 1)
            ):
                # Skip this [ since the \! means the whole sequence should be literal
                result.append(text_with_placeholders[i])
                i += 1
                continue

            # Check if this is an image (preceded by non-escaped !)
            is_image = (
                i > 0
                and text_with_placeholders[i - 1] == "!"
                and not is_escaped(text_with_placeholders, i - 1)
            )

            # Find the matching ']', handling nested brackets and escaped characters
            j = i + 1
            bracket_depth = 1  # We're inside one opening bracket
            while j < len(text_with_placeholders) and bracket_depth > 0:
                if text_with_placeholders[j] == "\\" and j + 1 < len(text_with_placeholders):
                    # Skip escaped character (e.g., \] or \[)
                    j += 2
                elif text_with_placeholders[j] == "[":
                    bracket_depth += 1
                    j += 1
                elif text_with_placeholders[j] == "]":
                    bracket_depth -= 1
                    j += 1
                else:
                    j += 1

            if bracket_depth == 0 and j < len(text_with_placeholders):
                # Found matching ']', check if followed by '(' or '['
                # j is now pointing past the closing ']', so link text is from i+1 to j-1
                link_text = text_with_placeholders[i + 1 : j - 1]
                if j < len(text_with_placeholders) and text_with_placeholders[j] == "(":
                    # Inline link: [text](url)
                    # Find matching ')' with balanced counting, skipping escaped parens
                    k = j + 1

                    # Check for angle-bracketed URL: ](<...>)
                    if k < len(text_with_placeholders) and text_with_placeholders[k] == "<":
                        # Find matching '>' and skip parenthesis balancing
                        k += 1
                        while k < len(text_with_placeholders) and text_with_placeholders[k] != ">":
                            if text_with_placeholders[k] == "\\" and k + 1 < len(
                                text_with_placeholders
                            ):
                                k += 2  # Skip escaped character
                            else:
                                k += 1
                        if k < len(text_with_placeholders) and text_with_placeholders[k] == ">":
                            k += 1  # Skip the '>'
                            # Now look for the closing ')'
                            while (
                                k < len(text_with_placeholders)
                                and text_with_placeholders[k] in " \t"
                            ):
                                k += 1  # Skip optional whitespace
                            if k < len(text_with_placeholders) and text_with_placeholders[k] == ")":
                                k += 1  # Skip the ')'
                                # Found complete link/image with angle-bracketed URL
                                if is_image and result and result[-1] == "!":
                                    result.pop()
                                result.append(link_text)
                                i = k
                                continue
                    else:
                        # Regular URL without angle brackets
                        paren_depth = 1
                        while k < len(text_with_placeholders) and paren_depth > 0:
                            if text_with_placeholders[k] == "\\" and k + 1 < len(
                                text_with_placeholders
                            ):
                                # Skip escaped character (e.g., \) or \()
                                k += 2
                            elif text_with_placeholders[k] == "(":
                                paren_depth += 1
                                k += 1
                            elif text_with_placeholders[k] == ")":
                                paren_depth -= 1
                                k += 1
                            else:
                                k += 1

                        if paren_depth == 0:
                            # Found complete link or image [text](url) or ![alt](src)
                            # For images, remove the preceding '!' that was already added
                            if is_image and result and result[-1] == "!":
                                result.pop()
                            result.append(link_text)
                            i = k
                            continue
                elif j < len(text_with_placeholders) and text_with_placeholders[j] == "[":
                    # Reference-style link: [text][ref] or [text][]
                    k = j + 1
                    # Find the matching ']'
                    while k < len(text_with_placeholders) and text_with_placeholders[k] != "]":
                        if text_with_placeholders[k] == "\\" and k + 1 < len(
                            text_with_placeholders
                        ):
                            k += 2  # Skip escaped character
                        else:
                            k += 1
                    if k < len(text_with_placeholders) and text_with_placeholders[k] == "]":
                        k += 1  # Skip the ']'
                        # Found complete reference-style link/image
                        if is_image and result and result[-1] == "!":
                            result.pop()
                        result.append(link_text)
                        i = k
                        continue

            # Not a valid link, keep the '['
            result.append(text_with_placeholders[i])
            i += 1
        else:
            result.append(text_with_placeholders[i])
            i += 1

    text_stripped = "".join(result)

    # Restore inline code spans
    for i, code_text in enumerate(inline_code_texts):
        text_stripped = text_stripped.replace(f"\x00CODE_{i}\x00", code_text)

    return text_stripped


def _leading_whitespace_columns(line: str) -> int:
    """
    Returns the number of visual columns occupied by the line's leading whitespace.
    Tabs advance to the next multiple of four columns to match Markdown indentation rules.
    """
    columns = 0
    for character in line:
        if character == " ":
            columns += 1
            continue
        if character == "\t":
            columns += 4 - (columns % 4)
            continue
        break
    return columns


def _try_open_fence(ctx: ParserContext, line: str) -> bool:
    """
    Try to open a fenced code block. Returns True if the line starts a fence.
    """
    if ctx.state is not ParserState.NORMAL:
        return False

    fence_match = CODE_FENCE_PATTERN.match(line)
    if not fence_match:
        return False

    indent_prefix = fence_match.group("indent") or ""
    indent_columns = _leading_whitespace_columns(indent_prefix)
    if indent_columns > CLOSING_FENCE_MAX_INDENT:
        return False

    fence_sequence = fence_match.group("fence")
    ctx.state = ParserState.IN_FENCED_CODE
    ctx.fence_char = fence_sequence[0]
    ctx.fence_length = len(fence_sequence)
    ctx.fence_indent_columns = indent_columns
    return True


def _try_close_fence(ctx: ParserContext, line: str) -> bool:
    """
    Try to close a fenced code block. Returns True if the line closes the current fence.
    """
    if ctx.state is not ParserState.IN_FENCED_CODE or ctx.fence_char is None:
        return False

    indent_columns = _leading_whitespace_columns(line)
    stripped_line = line.lstrip(" \t")
    if not stripped_line or stripped_line[0] != ctx.fence_char:
        return False

    fence_run_length = len(stripped_line) - len(stripped_line.lstrip(ctx.fence_char))
    if fence_run_length < ctx.fence_length:
        return False

    if stripped_line[fence_run_length:].strip():
        return False

    if indent_columns > CLOSING_FENCE_MAX_INDENT:
        return False

    ctx.state = ParserState.NORMAL
    ctx.fence_char = None
    ctx.fence_length = 0
    ctx.fence_indent_columns = 0
    return True


def _try_enter_indented_code(ctx: ParserContext, line: str) -> bool:
    """
    Try to enter an indented code block. Returns True if the line is indented code.
    """
    if ctx.state is not ParserState.NORMAL:
        return False

    if _leading_whitespace_columns(line) >= 4:
        ctx.state = ParserState.IN_INDENTED_CODE
        return True

    return False


def _try_exit_indented_code(ctx: ParserContext, line: str) -> bool:
    """
    Try to exit an indented code block. Returns True when the line should be skipped.
    """
    if ctx.state is not ParserState.IN_INDENTED_CODE:
        return False

    if line.strip() == "":
        return True

    if _leading_whitespace_columns(line) >= 4:
        return True

    ctx.state = ParserState.NORMAL
    return False


def parse_markdown(
    content: str, max_line_length: int | None = None, config: TocConfig | None = None
) -> ParseResult:
    """
    Parses markdown content and extracts headers and TOC markers.

    This is a pure function that takes string content and returns parsed results
    without any I/O operations.

    Args:
        content (str): The markdown content to parse.
        max_line_length (int | None): Override maximum allowed line length (excluding line endings).
        config (TocConfig | None): Configuration to use. Defaults to TocConfig().

    Returns:
        ParseResult: Parsed markdown with headers and TOC marker positions.

    Raises:
        LineTooLongError: If a line exceeds max_line_length.
        TooManyHeadersError: If the document has more headers than allowed.
    """
    config = config or TocConfig()
    validate_config(config)
    effective_max_line_length = (
        config.max_line_length if max_line_length is None else max_line_length
    )
    header_pattern = re.compile(rf"^(#{{{config.min_level},{config.max_level}}}) (.*)$")

    full_file = content.splitlines(keepends=True)

    # Pre-compute TOC coverage so we only skip validated sections.
    # IMPORTANT: Must track code blocks to avoid detecting markers inside them.
    toc_stack: list[int] = []
    toc_intervals: list[tuple[int, int]] = []
    precomp_ctx = ParserContext()

    for line_number, line in enumerate(full_file):
        # Check if we're inside a fenced code block
        if precomp_ctx.state is ParserState.IN_FENCED_CODE:
            _try_close_fence(precomp_ctx, line)
            continue

        # Check if this line opens a fenced code block
        if _try_open_fence(precomp_ctx, line):
            continue

        # Only detect TOC markers outside code blocks
        if line.startswith(config.start_marker):
            toc_stack.append(line_number)
        if line.startswith(config.end_marker) and toc_stack:
            start_index = toc_stack.pop()
            toc_intervals.append((start_index, line_number))

    toc_flags = [0] * (len(full_file) + 1)
    for start_index, end_index in toc_intervals:
        toc_flags[start_index + 1] += 1
        toc_flags[end_index + 1] -= 1

    is_line_in_toc: list[bool] = []
    depth = 0
    for idx in range(len(full_file)):
        depth += toc_flags[idx]
        is_line_in_toc.append(depth > 0)

    headers: list[str] = []
    toc_start_line: int | None = None
    toc_end_line: int | None = None

    ctx = ParserContext()

    for line_number, line in enumerate(full_file):
        # Tracks fenced code blocks (``` or ~~~, including info strings)
        if ctx.state is ParserState.IN_FENCED_CODE:
            _try_close_fence(ctx, line)
            continue

        if ctx.state is ParserState.IN_INDENTED_CODE:
            if _try_exit_indented_code(ctx, line):
                continue

        if _try_open_fence(ctx, line):
            continue

        # Tracks indented code blocks (any mix totaling 4+ columns)
        if _try_enter_indented_code(ctx, line):
            continue

        # Ignores code blocks and existing TOC header line
        if ctx.state is not ParserState.NORMAL or line.startswith(config.header_text):
            continue

        # Enforce line length outside TOC sections
        if not is_line_in_toc[line_number]:
            line_len = len(line)
            if line.endswith("\n"):
                line_len -= 1
                if line_len > 0 and line[line_len - 1] == "\r":
                    line_len -= 1
            if line_len > effective_max_line_length:
                raise LineTooLongError(line_number + 1, effective_max_line_length)

        # Finds headers
        header_match = header_pattern.match(line)
        if header_match:
            headers.append(header_match.group(0))

            # Check header count limit
            if len(headers) > config.max_headers:
                raise TooManyHeadersError(config.max_headers)

        # Finds TOC start and end line numbers
        if line.startswith(config.start_marker):
            toc_start_line = line_number
        if line.startswith(config.end_marker):
            toc_end_line = line_number

    return ParseResult(
        full_file=full_file,
        headers=headers,
        toc_start_line=toc_start_line,
        toc_end_line=toc_end_line,
    )
