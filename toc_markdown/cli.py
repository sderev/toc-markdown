"""
Generates a table of contents for a markdown file.
If an existing TOC is present, it updates it; otherwise, it outputs it to stdout.
"""

from __future__ import annotations

import os
import re
import stat
import string
import tempfile
import unicodedata
from pathlib import Path
from typing import TextIO

import click

# This pattern matches 2nd and 3rd level headers, but ignores 1st level headers.
HEADER_PATTERN = re.compile(r"^(#{2,3}) (.*)$")
CODE_FENCE_PATTERN = re.compile(r"^(?P<indent>\s{0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\((?:[^()]|\([^)]*\))*\)")
INLINE_CODE_PATTERN = re.compile(r"`[^`]+`")
CLOSING_FENCE_MAX_INDENT = 3

TOC_START_MARKER = "<!-- TOC -->"
TOC_END_MARKER = "<!-- /TOC -->"
MARKDOWN_EXTENSIONS = (".md", ".markdown")
CODE_FENCE = "```"
TOC_HEADER = "## Table of Contents"
MAX_FILE_SIZE_ENV_VAR = "TOC_MARKDOWN_MAX_FILE_SIZE"
DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MiB
MAX_LINE_LENGTH_ENV_VAR = "TOC_MARKDOWN_MAX_LINE_LENGTH"
DEFAULT_MAX_LINE_LENGTH = 10_000
MAX_HEADERS = 10_000
MAX_TOC_SECTION_LINES = MAX_HEADERS + 100  # allow slack for TOC metadata


@click.command()
@click.version_option()
@click.argument("filepath", type=click.Path(exists=True, dir_okay=False))
def cli(filepath: str):
    """
    Generates or updates the table of contents for the specified Markdown file.

    FILEPATH: The path to the Markdown file.

    Example: toc-markdown README.md
    """
    base_dir = Path.cwd().resolve()
    filepath = normalize_filepath(filepath, base_dir)
    max_file_size = get_max_file_size()
    max_line_length = get_max_line_length()
    initial_stat = collect_file_stat(filepath)
    enforce_file_size(initial_stat, max_file_size, filepath)

    full_file, headers, toc_start_line, toc_end_line = parse_file(filepath, max_line_length)
    post_parse_stat = collect_file_stat(filepath)
    ensure_file_unchanged(initial_stat, post_parse_stat, filepath)
    toc = generate_toc(headers)

    # Updates TOC
    if toc_start_line is not None and toc_end_line is not None:
        validate_toc_markers(toc_start_line, toc_end_line)
        update_toc(full_file, filepath, toc, toc_start_line, toc_end_line, post_parse_stat, initial_stat)
    # Inserts TOC
    else:
        print("".join(toc), end="")


def get_max_file_size() -> int:
    """
    Returns the maximum file size allowed for processing.

    The limit can be configured via the TOC_MARKDOWN_MAX_FILE_SIZE environment variable.
    """
    env_value = os.environ.get(MAX_FILE_SIZE_ENV_VAR)
    if env_value is None:
        return DEFAULT_MAX_FILE_SIZE

    try:
        max_size = int(env_value)
    except ValueError as error:
        error_message = (
            f"Invalid value for {MAX_FILE_SIZE_ENV_VAR}: "
            f"{click.style(env_value, fg='red')} (expected positive integer)"
        )
        raise click.ClickException(error_message) from error

    if max_size <= 0:
        error_message = (
            f"{MAX_FILE_SIZE_ENV_VAR} must be a positive integer, got "
            f"{click.style(str(max_size), fg='red')}."
        )
        raise click.ClickException(error_message)

    return max_size


def get_max_line_length() -> int:
    """
    Returns the maximum line length allowed for processing.

    The limit can be configured via the TOC_MARKDOWN_MAX_LINE_LENGTH environment variable.
    """
    env_value = os.environ.get(MAX_LINE_LENGTH_ENV_VAR)
    if env_value is None:
        return DEFAULT_MAX_LINE_LENGTH

    try:
        max_length = int(env_value)
    except ValueError as error:
        error_message = (
            f"Invalid value for {MAX_LINE_LENGTH_ENV_VAR}: "
            f"{click.style(env_value, fg='red')} (expected positive integer)"
        )
        raise click.ClickException(error_message) from error

    if max_length <= 0:
        error_message = (
            f"{MAX_LINE_LENGTH_ENV_VAR} must be a positive integer, got "
            f"{click.style(str(max_length), fg='red')}."
        )
        raise click.ClickException(error_message)

    return max_length


def normalize_filepath(raw_path: str, base_dir: Path) -> Path:
    """
    Validates and resolves a user-supplied filepath, ensuring that it is a markdown file
    located under the working directory and not backed by a symlink.
    """
    path = Path(raw_path).expanduser()

    if contains_symlink(path):
        error_message = f"Symlinks are not supported for security reasons: {click.style(str(path), fg='red')}"
        raise click.BadParameter(error_message)

    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as error:
        error_message = f"{click.style(str(path), fg='red')} does not exist."
        raise click.BadParameter(error_message) from error
    except OSError as error:
        error_message = f"Error resolving {click.style(str(path), fg='red')}: {click.style(str(error), fg='red')}"
        raise click.BadParameter(error_message) from error

    if not resolved.is_file():
        error_message = f"{click.style(str(resolved), fg='red')} is not a regular file."
        raise click.BadParameter(error_message)

    try:
        resolved.relative_to(base_dir)
    except ValueError as error:
        error_message = (
            f"{click.style(str(resolved), fg='red')} is outside of the working directory "
            f"{click.style(str(base_dir), fg='red')}."
        )
        raise click.BadParameter(error_message) from error

    if resolved.suffix.lower() not in MARKDOWN_EXTENSIONS:
        error_message = f"{click.style(f'{resolved} is not a Markdown file.', fg='red')}\n"
        error_message += f"Supported extensions are: {', '.join(MARKDOWN_EXTENSIONS)}"
        raise click.BadParameter(error_message)

    return resolved


def contains_symlink(path: Path) -> bool:
    """
    Returns True if the provided path or any of its parents is a symlink.
    """
    for candidate in (path, *path.parents):
        try:
            if candidate.is_symlink():
                return True
        except OSError:
            continue
    return False


def collect_file_stat(filepath: Path) -> os.stat_result:
    """
    Returns the stat information of the specified file while ensuring it is a regular file.
    """
    try:
        stat_result = os.stat(filepath, follow_symlinks=False)
    except OSError as error:
        error_message = f"Error accessing {filepath}: {click.style(str(error), fg='red')}"
        raise IOError(error_message) from error

    if stat.S_ISLNK(stat_result.st_mode):
        error_message = f"Symlinks are not supported: {click.style(str(filepath), fg='red')}."
        raise IOError(error_message)

    if not stat.S_ISREG(stat_result.st_mode):
        error_message = f"{click.style(str(filepath), fg='red')} is not a regular file."
        raise IOError(error_message)

    return stat_result


def enforce_file_size(stat_result: os.stat_result, max_size: int, filepath: Path):
    """
    Ensures the file size does not exceed the configured maximum.
    """
    if stat_result.st_size > max_size:
        error_message = (
            f"{click.style(str(filepath), fg='red')} exceeds the maximum allowed size of "
            f"{click.style(str(max_size), fg='red')} bytes."
        )
        raise IOError(error_message)


def ensure_file_unchanged(
    expected_stat: os.stat_result, current_stat: os.stat_result, filepath: Path
):
    """
    Ensures that the file has not changed between operations to avoid race conditions.
    """
    fingerprint_before = (
        getattr(expected_stat, "st_ino", None),
        getattr(expected_stat, "st_dev", None),
        expected_stat.st_size,
        expected_stat.st_mtime_ns,
    )
    fingerprint_after = (
        getattr(current_stat, "st_ino", None),
        getattr(current_stat, "st_dev", None),
        current_stat.st_size,
        current_stat.st_mtime_ns,
    )

    if fingerprint_before != fingerprint_after:
        error_message = (
            f"{click.style(str(filepath), fg='red')} changed during processing; refusing to overwrite."
        )
        raise IOError(error_message)


def safe_read(filepath: Path) -> TextIO:
    """
    Opens a file and handles any errors.

    Args:
        filepath (Path): The path to the file.

    Returns:
        TextIO: A file object opened for reading.
    """
    try:
        return open(filepath, "r", encoding="UTF-8")
    except (
        FileNotFoundError,
        PermissionError,
        IsADirectoryError,
        NotADirectoryError,
    ) as error:
        error_message = f"Error accessing {filepath}: {click.style(str(error), fg='red')}"
        raise IOError(error_message) from error


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



def _enforce_line_length(
    line: str, line_number: int, filepath: Path, max_line_length: int
) -> None:
    """
    Ensures a single line does not exceed the configured maximum length.
    """
    line_len = len(line)
    if line.endswith("\n"):
        line_len -= 1
        if line_len > 0 and line[line_len - 1] == "\r":
            line_len -= 1
    if line_len > max_line_length:
        error_message = (
            f"{click.style(str(filepath), fg='red')} contains a line at line {line_number + 1} "
            f"exceeding the maximum allowed length of {click.style(str(max_line_length), fg='red')} "
            "characters."
        )
        raise IOError(error_message)


def parse_file(
    filepath: Path, max_line_length: int = DEFAULT_MAX_LINE_LENGTH
) -> tuple[list[str], list[str], int | None, int | None]:
    """
    Parses the specified Markdown file.

    Args:
        filepath (Path): The path to the markdown file.
        max_line_length (int): Maximum allowed line length (excluding line endings).

    Returns:
        tuple: A tuple containing:
            - full_file: A list of lines in the file.
            - headers: A list of headers found in the file.
            - toc_start_line: The line number where the TOC starts, or None if not found.
            - toc_end_line: The line number where the TOC ends, or None if not found.
    """
    full_file: list[str] = []

    try:
        with safe_read(filepath) as file:
            for line in file:
                full_file.append(line)
    except UnicodeDecodeError as error:
        error_message = f"Invalid UTF-8 sequence in {filepath}: {click.style(str(error), fg='red')}"
        raise IOError(error_message) from error

    # Pre-compute TOC coverage so we only skip validated sections.
    # IMPORTANT: Must track code blocks to avoid detecting markers inside them.
    toc_stack: list[int] = []
    toc_intervals: list[tuple[int, int]] = []
    precomp_fence_char: str | None = None
    precomp_fence_length = 0
    precomp_fence_indent_columns = 0

    for line_number, line in enumerate(full_file):
        # Check if we're inside a fenced code block
        if precomp_fence_char is not None:
            # Try to close the fence
            indent_columns = _leading_whitespace_columns(line)
            stripped_line = line.lstrip(" \t")
            if stripped_line and stripped_line[0] == precomp_fence_char:
                fence_run_length = len(stripped_line) - len(stripped_line.lstrip(precomp_fence_char))
                if fence_run_length >= precomp_fence_length and stripped_line[fence_run_length:].strip() == "":
                    additional_indent = indent_columns - precomp_fence_indent_columns
                    if additional_indent <= CLOSING_FENCE_MAX_INDENT:
                        precomp_fence_char = None
                        precomp_fence_length = 0
                        precomp_fence_indent_columns = 0
            continue

        # Check if this line opens a fenced code block
        fence_match = CODE_FENCE_PATTERN.match(line)
        if fence_match:
            fence_sequence = fence_match.group("fence")
            precomp_fence_char = fence_sequence[0]
            precomp_fence_length = len(fence_sequence)
            indent_prefix = fence_match.group("indent") or ""
            precomp_fence_indent_columns = _leading_whitespace_columns(indent_prefix)
            continue

        # Only detect TOC markers outside code blocks
        if line.startswith(TOC_START_MARKER):
            toc_stack.append(line_number)
        if line.startswith(TOC_END_MARKER) and toc_stack:
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

    # Flags for code blocks
    code_fence_char: str | None = None
    code_fence_length = 0
    code_fence_indent_columns = 0
    is_in_indented_code_block = False

    for line_number, line in enumerate(full_file):
        # Tracks fenced code blocks (``` or ~~~, including info strings)
        if code_fence_char is not None:
            indent_columns = _leading_whitespace_columns(line)
            stripped_line = line.lstrip(" 	")
            if not stripped_line or stripped_line[0] != code_fence_char:
                continue

            fence_run_length = len(stripped_line) - len(stripped_line.lstrip(code_fence_char))

            if fence_run_length >= code_fence_length and stripped_line[fence_run_length:].strip() == "":
                additional_indent = indent_columns - code_fence_indent_columns
                if additional_indent <= CLOSING_FENCE_MAX_INDENT:
                    code_fence_char = None
                    code_fence_length = 0
                    code_fence_indent_columns = 0

            continue

        fence_match = CODE_FENCE_PATTERN.match(line)
        if fence_match:
            fence_sequence = fence_match.group("fence")
            code_fence_char = fence_sequence[0]
            code_fence_length = len(fence_sequence)
            indent_prefix = fence_match.group("indent") or ""
            code_fence_indent_columns = _leading_whitespace_columns(indent_prefix)
            is_in_indented_code_block = False
            continue

        # Tracks indented code blocks (any mix totaling 4+ columns)
        leading_columns = _leading_whitespace_columns(line)
        if leading_columns >= 4:
            is_in_indented_code_block = True
            continue
        if is_in_indented_code_block:
            if line.strip() == "":
                continue
            is_in_indented_code_block = False

        # Ignores code blocks and existing TOC header line
        if (
            code_fence_char is not None
            or is_in_indented_code_block
            or line.startswith(TOC_HEADER)
        ):
            continue

        if not is_line_in_toc[line_number]:
            _enforce_line_length(line, line_number, filepath, max_line_length)

        # Finds headers
        header_match = HEADER_PATTERN.match(line)
        if header_match:
            headers.append(header_match.group(0))

            # Check header count limit
            if len(headers) > MAX_HEADERS:
                error_message = (
                    f"{click.style(str(filepath), fg='red')} contains too many headers "
                    f"(limit: {click.style(str(MAX_HEADERS), fg='red')})."
                )
                raise IOError(error_message)

        # Finds TOC start and end line numbers
        if line.startswith(TOC_START_MARKER):
            toc_start_line = line_number
        if line.startswith(TOC_END_MARKER):
            toc_end_line = line_number

    return full_file, headers, toc_start_line, toc_end_line


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
                    close_start = i
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
            if i > 0 and text_with_placeholders[i - 1] == "!" and is_escaped(text_with_placeholders, i - 1):
                # Skip this [ since the \! means the whole sequence should be literal
                result.append(text_with_placeholders[i])
                i += 1
                continue

            # Check if this is an image (preceded by non-escaped !)
            is_image = i > 0 and text_with_placeholders[i - 1] == "!" and not is_escaped(text_with_placeholders, i - 1)
            image_start = i - 1 if is_image else i

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
                            if text_with_placeholders[k] == "\\" and k + 1 < len(text_with_placeholders):
                                k += 2  # Skip escaped character
                            else:
                                k += 1
                        if k < len(text_with_placeholders) and text_with_placeholders[k] == ">":
                            k += 1  # Skip the '>'
                            # Now look for the closing ')'
                            while k < len(text_with_placeholders) and text_with_placeholders[k] in " \t":
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
                            if text_with_placeholders[k] == "\\" and k + 1 < len(text_with_placeholders):
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
                        if text_with_placeholders[k] == "\\" and k + 1 < len(text_with_placeholders):
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
    slug = title.casefold().translate(str.maketrans("", "", punctuation)).strip()

    slug = re.sub(r"\s+", "-", slug)
    slug = unicodedata.normalize("NFKD", slug).encode("ascii", "ignore").decode("utf-8", "ignore")
    slug = slug.casefold()
    slug = slug.translate(str.maketrans("", "", punctuation))
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")

    return slug if slug else "untitled"


def generate_toc(headers: list[str]) -> list[str]:
    """
    Generates a table of contents from a list of headers.

    Args:
        headers (list): A list of markdown headers.

    Returns:
        list: A list of lines that make up the TOC.
    """
    toc = [f"{TOC_START_MARKER}\n", "## Table of Contents\n\n"]

    for heading in headers:
        # Count only leading # characters, not all # in the string (e.g., URLs with #anchor)
        level = len(heading) - len(heading.lstrip("#"))
        title = heading[level:].strip()
        title = strip_markdown_links(title)
        link = generate_slug(title)
        toc.append("    " * (level - 2) + f"1. [{title}](#{link})" + "\n")

    toc.append(f"{TOC_END_MARKER}" + "\n")

    return toc


def validate_toc_markers(toc_start_line: int, toc_end_line: int) -> None:
    """Ensure TOC markers are sane before mutating the file."""

    if toc_start_line >= toc_end_line:
        raise click.BadParameter(
            "Invalid TOC markers:\n"
            f"  Start marker at line {toc_start_line + 1}\n"
            f"  End marker at line {toc_end_line + 1}\n"
            "Start marker must come before end marker."
        )

    toc_size = toc_end_line - toc_start_line
    if toc_size > MAX_TOC_SECTION_LINES:
        raise click.BadParameter(f"TOC section is suspiciously large ({toc_size} lines)")


def update_toc(
    full_file: list[str],
    filepath: Path,
    toc: list[str],
    toc_start_line: int,
    toc_end_line: int,
    expected_stat: os.stat_result,
    initial_stat: os.stat_result,
):
    """
    Updates the table of contents in the specified Markdown file.

    Args:
        full_file (list): A list of lines in the file.
        filepath (Path): The path to the markdown file.
        toc (list): A list of lines that make up the TOC.
        toc_start_line (int): The line number where the TOC starts.
        toc_end_line (int): The line number where the TOC ends.
        expected_stat (os.stat_result): The file stat after parsing (for race detection).
        initial_stat (os.stat_result): The file stat before parsing (for atime preservation).
    """
    current_stat = collect_file_stat(filepath)
    ensure_file_unchanged(expected_stat, current_stat, filepath)

    # Capture all metadata for preservation
    permissions = stat.S_IMODE(expected_stat.st_mode)
    uid = getattr(expected_stat, "st_uid", None)
    gid = getattr(expected_stat, "st_gid", None)
    # Use atime from BEFORE the file was read to preserve original access time
    atime_ns = initial_stat.st_atime_ns

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="UTF-8", delete=False, dir=filepath.parent
    ) as tmp_file:
        # Write the file up to the TOC start line
        for line in full_file[:toc_start_line]:
            tmp_file.write(line)

        # Write the new TOC
        for line in toc:
            tmp_file.write(line)

        # Write the rest of the file after the TOC end line
        tmp_file.writelines(full_file[toc_end_line + 1 :])

        # Ensure the temporary file is flushed, synced, and has the original permissions
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
        os.chmod(tmp_file.name, permissions)

        # Attempt to preserve ownership (requires privileges and platform support)
        if uid is not None and gid is not None and hasattr(os, "chown"):
            try:
                os.chown(tmp_file.name, uid, gid)
            except PermissionError:
                click.echo(
                    f"Warning: Could not preserve file ownership for {filepath.name} "
                    "(requires elevated privileges)",
                    err=True,
                )

    # Replace the original file with the temporary file (atomic operation)
    os.replace(tmp_file.name, filepath)

    # Preserve access time (mtime intentionally NOT preserved to reflect actual modification)
    # We read the new mtime from the replaced file and restore only the original atime
    current_stat = filepath.stat()
    os.utime(filepath, ns=(atime_ns, current_stat.st_mtime_ns))


if __name__ == "__main__":
    cli()
