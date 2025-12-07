"""Markdown parsing utilities."""

from __future__ import annotations

import re
from pathlib import Path

from .config import ConfigError, TocConfig, validate_config
from .constants import CLOSING_FENCE_MAX_INDENT, CODE_FENCE_PATTERN
from .exceptions import LineTooLongError, ParseError, TooManyHeadersError
from .filesystem import safe_read
from .models import ParseResult, ParserContext, ParserState


def is_escaped(text: str, pos: int) -> bool:
    """Determine whether a character is escaped by preceding backslashes.

    Counts consecutive backslashes immediately before `pos`; an odd count marks
    the character as escaped.

    Args:
        text: Text containing the character.
        pos: Zero-based index of the character to inspect.

    Returns:
        bool: True when the character is escaped, otherwise False.

    Examples:
        is_escaped("\\\\*", 2)  # False, two backslashes
        is_escaped("\\*", 1)  # True, one backslash
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
    """Locate inline code spans using CommonMark-style backticks.

    Inline spans must start and end with backtick sequences of equal length;
    both delimiters must be unescaped.

    Args:
        text: The text to scan for inline code spans.

    Returns:
        list[tuple[int, int]]: Start (inclusive) and end (exclusive) positions
            for each inline code span.

    Examples:
        find_inline_code_spans("`code`")  # [(0, 6)]
        find_inline_code_spans("``more`` text")  # [(0, 8)]
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
    r"""Remove Markdown link and image syntax while preserving visible text.

    Link markers inside inline code are left intact, and escaped image markers
    (``\!``) remain literal. Nested parentheses, angle-bracket URLs, and
    reference-style links are handled.

    Args:
        text: Text potentially containing Markdown links.

    Returns:
        str: Text with link and image syntax removed while keeping the link text.

    Examples:
        strip_markdown_links("[title](https://example.com)")  # "title"
        strip_markdown_links("`[code](x)` and [title](y)")  # "`[code](x)` and title"
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
    """Compute the column width of leading whitespace.

    Tabs advance to the next multiple of four columns to match Markdown
    indentation rules.

    Args:
        line: Line whose leading whitespace should be measured.

    Returns:
        int: Number of columns occupied by the leading whitespace.

    Examples:
        _leading_whitespace_columns("    text")  # 4
        _leading_whitespace_columns("\ttext")  # 4
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
    """Detect the start of a fenced code block.

    Args:
        ctx: Parser context to update when a fence opens.
        line: Current line being scanned.

    Returns:
        bool: True when the line begins a fence and the context is updated.

    Examples:
        _try_open_fence(ParserContext(), "```python\n")  # True
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
    """Attempt to close the active fenced code block.

    Args:
        ctx: Parser context describing the active fence.
        line: Current line being scanned.

    Returns:
        bool: True when the line closes the fence; otherwise False.

    Examples:
        ctx = ParserContext(state=ParserState.IN_FENCED_CODE, fence_char="`", fence_length=3)
        _try_close_fence(ctx, "```\n")
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
    """Detect entry into an indented code block.

    Args:
        ctx: Parser context to update.
        line: Line being scanned.

    Returns:
        bool: True when the line starts indented code; otherwise False.

    Examples:
        _try_enter_indented_code(ParserContext(), "    indented")
    """
    if ctx.state is not ParserState.NORMAL:
        return False

    if _leading_whitespace_columns(line) >= 4:
        ctx.state = ParserState.IN_INDENTED_CODE
        return True

    return False


def _try_exit_indented_code(ctx: ParserContext, line: str) -> bool:
    """Determine whether to leave an indented code block.

    Args:
        ctx: Parser context to update.
        line: Line being scanned.

    Returns:
        bool: True when the parser should remain in code mode for the line
            (blank or still indented); False when the parser should resume
            normal processing.

    Examples:
        ctx = ParserContext(state=ParserState.IN_INDENTED_CODE)
        _try_exit_indented_code(ctx, "next line")
    """
    if ctx.state is not ParserState.IN_INDENTED_CODE:
        return False

    if line.strip() == "":
        return True

    if _leading_whitespace_columns(line) >= 4:
        return True

    ctx.state = ParserState.NORMAL
    return False


def _try_enter_toc(
    ctx: ParserContext, line_number: int, toc_start_to_end: dict[int, int], toc_end_stack: list[int]
) -> bool:
    """Enter TOC state when the current line starts a validated TOC block.

    Args:
        ctx: Parser context to update.
        line_number: Zero-based line number being scanned.
        toc_start_to_end: Mapping of TOC start line numbers to their matching end lines.
        toc_end_stack: Stack of TOC end line numbers tracking nested TOC regions.

    Returns:
        bool: True when the parser enters (or remains in) a TOC region.
    """
    end_line = toc_start_to_end.get(line_number)
    if end_line is None:
        return False

    toc_end_stack.append(end_line)
    ctx.state = ParserState.IN_TOC
    return True


def _try_exit_toc(ctx: ParserContext, line_number: int, toc_end_stack: list[int]) -> bool:
    """Exit TOC state when reaching the matching end marker line.

    Args:
        ctx: Parser context to update.
        line_number: Zero-based line number being scanned.
        toc_end_stack: Stack of TOC end line numbers tracking nested TOC regions.

    Returns:
        bool: True when the parser exits a TOC region for the current line.
    """
    if not toc_end_stack or line_number != toc_end_stack[-1]:
        return False

    toc_end_stack.pop()
    ctx.state = ParserState.IN_TOC if toc_end_stack else ParserState.NORMAL
    return True


def parse_markdown(
    content: str, max_line_length: int | None = None, config: TocConfig | None = None
) -> ParseResult:
    """Parse Markdown content to extract headers and TOC markers.

    Ignores TOC markers and headers inside code blocks or validated TOC
    sections, and enforces header and line-length limits based on the provided
    configuration.

    Args:
        content: The markdown content to parse.
        max_line_length: Optional override for the maximum allowed line length
            (excluding line endings).
        config: Configuration controlling parsing behavior. Defaults to a new
            `TocConfig` when omitted.

    Returns:
        ParseResult: File lines, parsed headers, and TOC marker positions. Marker
            indices are None when no matching marker is found.

    Raises:
        ConfigError: If the configuration fails validation.
        LineTooLongError: If a non-TOC line exceeds `max_line_length`.
        TooManyHeadersError: If the document has more headers than allowed.

    Examples:
        parse_markdown("# Title\\n\\n## Section\\n", max_line_length=80)
    """
    config = config or TocConfig()
    validate_config(config)
    effective_max_line_length = (
        config.max_line_length if max_line_length is None else max_line_length
    )
    header_pattern = re.compile(rf"^(#{{{config.min_level},{config.max_level}}}) (.*)$")

    full_file = content.splitlines(keepends=True)

    # Pre-compute TOC coverage so we only skip validated sections.
    # IMPORTANT: Must track both fenced and indented code blocks to avoid
    # detecting markers inside them.
    toc_stack: list[int] = []
    toc_intervals: list[tuple[int, int]] = []
    precomp_ctx = ParserContext()

    for line_number, line in enumerate(full_file):
        if precomp_ctx.state is ParserState.IN_FENCED_CODE:
            _try_close_fence(precomp_ctx, line)
            continue

        if precomp_ctx.state is ParserState.IN_INDENTED_CODE:
            if _try_exit_indented_code(precomp_ctx, line):
                continue

        if _try_open_fence(precomp_ctx, line):
            continue

        if _try_enter_indented_code(precomp_ctx, line):
            continue

        if line.startswith(config.start_marker):
            toc_stack.append(line_number)
        if line.startswith(config.end_marker) and toc_stack:
            start_index = toc_stack.pop()
            toc_intervals.append((start_index, line_number))

    toc_start_to_end = {start: end for start, end in toc_intervals}

    headers: list[str] = []
    toc_start_line: int | None = None
    toc_end_line: int | None = None

    ctx = ParserContext()
    toc_end_stack: list[int] = []

    for line_number, line in enumerate(full_file):
        # Tracks fenced code blocks (``` or ~~~, including info strings)
        if ctx.state is ParserState.IN_FENCED_CODE:
            _try_close_fence(ctx, line)
            continue

        if ctx.state is ParserState.IN_INDENTED_CODE:
            if _try_exit_indented_code(ctx, line):
                continue

        if ctx.state is ParserState.IN_TOC:
            if _try_enter_toc(ctx, line_number, toc_start_to_end, toc_end_stack):
                toc_start_line = line_number
                continue

            if _try_exit_toc(ctx, line_number, toc_end_stack):
                toc_end_line = line_number
                continue

            continue

        if _try_open_fence(ctx, line):
            continue

        # Tracks indented code blocks (any mix totaling 4+ columns)
        if _try_enter_indented_code(ctx, line):
            continue

        # Ignores existing TOC header line
        if line.startswith(config.header_text):
            continue

        # Enforce line length outside TOC sections
        line_len = len(line)
        if line.endswith("\n"):
            line_len -= 1
            if line_len > 0 and line[line_len - 1] == "\r":
                line_len -= 1
        if line_len > effective_max_line_length:
            raise LineTooLongError(line_number + 1, effective_max_line_length)

        if line.startswith(config.start_marker):
            toc_start_line = line_number
            if _try_enter_toc(ctx, line_number, toc_start_to_end, toc_end_stack):
                continue

        if line.startswith(config.end_marker):
            toc_end_line = line_number
            continue

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


class ParseFileError(Exception):
    """Raised when parsing a Markdown file fails."""


def parse_file(
    filepath: Path,
    max_line_length: int | None = None,
    config: TocConfig | None = None,
) -> tuple[list[str], list[str], int | None, int | None]:
    """Parse a Markdown file and extract TOC metadata.

    Args:
        filepath: Path to the markdown file to parse.
        max_line_length: Optional override for the maximum allowed line length
            (excluding line endings).
        config: Configuration controlling parsing behavior; defaults to a new
            `TocConfig` when omitted.

    Returns:
        tuple[list[str], list[str], int | None, int | None]: Full file content as
            lines, parsed headers, TOC start line index, and TOC end line index.
            The TOC indices are None when no existing TOC markers are present.

    Raises:
        ParseFileError: If configuration is invalid, parsing fails because of
            limits or malformed content, or the file cannot be read or decoded.

    Examples:
        full_file, headers, toc_start, toc_end = parse_file(Path("README.md"), 120, config)
    """
    config = config or TocConfig()
    try:
        validate_config(config)
    except ConfigError as error:
        raise ParseFileError(str(error)) from error

    effective_max_line_length = (
        config.max_line_length if max_line_length is None else max_line_length
    )
    if effective_max_line_length <= 0:
        raise ParseFileError("`max_line_length` override must be a positive integer")

    # Read file content
    try:
        with safe_read(filepath) as file:
            content = file.read()
    except UnicodeDecodeError as error:
        error_message = f"Invalid UTF-8 sequence in {filepath}: {error}"
        raise ParseFileError(error_message) from error
    except IOError as error:
        raise ParseFileError(str(error)) from error

    # Parse content using pure function
    try:
        result = parse_markdown(content, effective_max_line_length, config)
    except LineTooLongError as error:
        error_message = (
            f"{filepath} contains a line at line {error.line_number} "
            f"exceeding the maximum allowed length of {error.max_line_length} characters."
        )
        raise ParseFileError(error_message) from error
    except TooManyHeadersError as error:
        error_message = f"{filepath} contains too many headers (limit: {error.limit})."
        raise ParseFileError(error_message) from error
    except ParseError as error:
        error_message = f"{filepath}: {error}"
        raise ParseFileError(error_message) from error

    # Return as tuple for backward compatibility with existing code
    return result.full_file, result.headers, result.toc_start_line, result.toc_end_line
