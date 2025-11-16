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

# Re-exports for backward compatibility during refactoring
from .constants import (  # noqa: F401
    CLOSING_FENCE_MAX_INDENT,
    CODE_FENCE_PATTERN,
    HEADER_PATTERN,
    MAX_HEADERS,
    MAX_TOC_SECTION_LINES,
    TOC_END_MARKER,
    TOC_HEADER,
    TOC_START_MARKER,
)
from .generator import generate_toc_entries as generate_toc, validate_toc_markers  # noqa: F401
from .models import ParseResult  # noqa: F401
from .parser import (  # noqa: F401
    find_inline_code_spans,
    is_escaped,
    parse_markdown,
    strip_markdown_links,
)
from .slugify import generate_slug  # noqa: F401

# CLI-specific patterns (not used by pure business logic modules)
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\((?:[^()]|\([^)]*\))*\)")
INLINE_CODE_PATTERN = re.compile(r"`[^`]+`")

MARKDOWN_EXTENSIONS = (".md", ".markdown")
CODE_FENCE = "```"
MAX_FILE_SIZE_ENV_VAR = "TOC_MARKDOWN_MAX_FILE_SIZE"
DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MiB
MAX_LINE_LENGTH_ENV_VAR = "TOC_MARKDOWN_MAX_LINE_LENGTH"
DEFAULT_MAX_LINE_LENGTH = 10_000


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
        try:
            validate_toc_markers(toc_start_line, toc_end_line)
        except ValueError as error:
            raise click.BadParameter(str(error)) from error
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

    This is a wrapper around parse_markdown() that handles I/O and Click error formatting.

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
    # Read file content
    try:
        with safe_read(filepath) as file:
            content = file.read()
    except UnicodeDecodeError as error:
        error_message = f"Invalid UTF-8 sequence in {filepath}: {click.style(str(error), fg='red')}"
        raise IOError(error_message) from error

    # Parse content using pure function
    try:
        result = parse_markdown(content, max_line_length)
    except ValueError as error:
        # Convert ValueError to IOError with Click styling and filepath context
        error_message = str(error)
        if "exceeds maximum allowed length" in error_message:
            # Extract line number from error message
            error_message = (
                f"{click.style(str(filepath), fg='red')} contains a line {error_message.split('Line ')[1].split(' exceeds')[0]} "
                f"exceeding the maximum allowed length of {click.style(str(max_line_length), fg='red')} "
                "characters."
            )
        elif "Too many headers" in error_message:
            error_message = (
                f"{click.style(str(filepath), fg='red')} contains too many headers "
                f"(limit: {click.style(str(MAX_HEADERS), fg='red')})."
            )
        else:
            error_message = f"{click.style(str(filepath), fg='red')}: {error_message}"
        raise IOError(error_message) from error

    # Return as tuple for backward compatibility with existing code
    return result.full_file, result.headers, result.toc_start_line, result.toc_end_line


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
