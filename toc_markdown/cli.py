"""
Generates a table of contents for a markdown file.
If an existing TOC is present, it updates it; otherwise, it outputs it to stdout.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import TextIO

import click
from dataclasses import replace

from .config import ConfigError, TocConfig, load_config, validate_config
from .constants import (
    CLOSING_FENCE_MAX_INDENT,
    CODE_FENCE_PATTERN,
    DEFAULT_CONFIG,
    MAX_HEADERS,
    MAX_TOC_SECTION_LINES,
    TOC_END_MARKER,
    TOC_HEADER,
    TOC_START_MARKER,
)
from .exceptions import LineTooLongError, ParseError, TooManyHeadersError
from .generator import generate_toc_entries as generate_toc
from .generator import validate_toc_markers
from .parser import find_inline_code_spans, is_escaped, parse_markdown, strip_markdown_links
from .slugify import generate_slug

MARKDOWN_EXTENSIONS = (".md", ".markdown")
CODE_FENCE = "```"
MAX_FILE_SIZE_ENV_VAR = "TOC_MARKDOWN_MAX_FILE_SIZE"
DEFAULT_MAX_FILE_SIZE = DEFAULT_CONFIG.max_file_size
MAX_LINE_LENGTH_ENV_VAR = "TOC_MARKDOWN_MAX_LINE_LENGTH"
DEFAULT_MAX_LINE_LENGTH = DEFAULT_CONFIG.max_line_length

__all__ = [
    "cli",
    "parse_file",
    "generate_toc",
    "generate_slug",
    "parse_markdown",
    "strip_markdown_links",
    "find_inline_code_spans",
    "is_escaped",
    "TOC_START_MARKER",
    "TOC_END_MARKER",
    "TOC_HEADER",
    "CODE_FENCE",
    "MAX_TOC_SECTION_LINES",
    "CODE_FENCE_PATTERN",
    "CLOSING_FENCE_MAX_INDENT",
    "MAX_HEADERS",
]


def apply_overrides(config: TocConfig, **overrides: object) -> TocConfig:
    """Apply override values to a `TocConfig`.

    Args:
        config: Base configuration to update.
        overrides: Override values keyed by configuration field name; values set to
            None are ignored.

    Returns:
        TocConfig: New configuration with the provided overrides applied. The
            original configuration is returned when no changes are supplied.

    Raises:
        TypeError: If an override name is not defined on `TocConfig`.

    Examples:
        updated = apply_overrides(config, header_text="Contents", min_level=2)
    """
    changes = {key: value for key, value in overrides.items() if value is not None}
    if not changes:
        return config
    return replace(config, **changes)


def build_config(search_path: Path, **overrides: object) -> TocConfig:
    """Load, override, and validate configuration.

    Args:
        search_path: Directory where configuration files are resolved.
        overrides: Override values keyed by configuration attributes; None values
            are ignored.

    Returns:
        TocConfig: Validated configuration ready for parsing.

    Raises:
        ConfigError: If configuration loading or validation fails.

    Examples:
        config = build_config(Path.cwd(), min_level=2, list_style="-")
    """
    config = load_config(search_path)
    config = apply_overrides(config, **overrides)
    validate_config(config)
    return config


@click.command()
@click.version_option()
@click.option("--start-marker", help="TOC start marker")
@click.option("--end-marker", help="TOC end marker")
@click.option("--header-text", help="TOC header text")
@click.option("--min-level", type=int, help="Minimum header level")
@click.option("--max-level", type=int, help="Maximum header level")
@click.option("--indent-chars", help="Indentation characters")
@click.option("--list-style", type=click.Choice(["1.", "*", "-"]), help="List style (1. or * or -)")
@click.argument("filepath", type=click.Path(exists=True, dir_okay=False))
def cli(
    filepath: str,
    start_marker: str | None = None,
    end_marker: str | None = None,
    header_text: str | None = None,
    min_level: int | None = None,
    max_level: int | None = None,
    indent_chars: str | None = None,
    list_style: str | None = None,
):
    """
    Entry point for generating or updating a Markdown table of contents.

    Args:
        filepath: Path to the Markdown file to process.
        start_marker: Override for the TOC start marker.
        end_marker: Override for the TOC end marker.
        header_text: Replacement text for the TOC header.
        min_level: Smallest header level to include.
        max_level: Largest header level to include.
        indent_chars: Indentation characters for nested entries.
        list_style: Bullet style to use (`1.`, `*`, or `-`).

    Returns:
        None.

    Raises:
        click.BadParameter: If CLI parameters reference invalid paths or contain
            unsupported overrides, including invalid configuration values.
        click.ClickException: If parsing fails due to limits or malformed content.
        IOError: If filesystem safety checks fail or the target cannot be accessed.

    Examples:
        toc-markdown README.md --min-level 2 --list-style "-"
    """
    base_dir = Path.cwd().resolve()
    filepath = normalize_filepath(filepath, base_dir)
    try:
        config = build_config(
            filepath.parent,
            start_marker=start_marker,
            end_marker=end_marker,
            header_text=header_text,
            min_level=min_level,
            max_level=max_level,
            indent_chars=indent_chars,
            list_style=list_style,
        )
    except ConfigError as error:
        raise click.BadParameter(str(error)) from error

    max_file_size = get_max_file_size(default=config.max_file_size)
    max_line_length = get_max_line_length(default=config.max_line_length)
    initial_stat = collect_file_stat(filepath)
    enforce_file_size(initial_stat, max_file_size, filepath)

    full_file, headers, toc_start_line, toc_end_line = parse_file(
        filepath, max_line_length, config
    )
    post_parse_stat = collect_file_stat(filepath)
    ensure_file_unchanged(initial_stat, post_parse_stat, filepath)
    toc = generate_toc(headers, config)

    # Updates TOC
    if toc_start_line is not None and toc_end_line is not None:
        try:
            validate_toc_markers(toc_start_line, toc_end_line, config)
        except ValueError as error:
            raise click.BadParameter(str(error)) from error
        update_toc(
            full_file, filepath, toc, toc_start_line, toc_end_line, post_parse_stat, initial_stat
        )
    # Inserts TOC
    else:
        print("".join(toc), end="")


def get_max_file_size(default: int = DEFAULT_MAX_FILE_SIZE) -> int:
    """Resolve the maximum allowed file size.

    Args:
        default: Fallback value in bytes when the environment variable is unset.

    Returns:
        int: Maximum allowed file size in bytes.

    Raises:
        click.ClickException: If the environment value is not a positive integer.

    Examples:
        os.environ["TOC_MARKDOWN_MAX_FILE_SIZE"] = "204800"
        limit = get_max_file_size(default=102400)
    """
    env_value = os.environ.get(MAX_FILE_SIZE_ENV_VAR)
    if env_value is None:
        return default

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


def get_max_line_length(default: int = DEFAULT_MAX_LINE_LENGTH) -> int:
    """Resolve the maximum allowed line length.

    Args:
        default: Fallback value in characters when the environment variable is
            unset.

    Returns:
        int: Maximum allowed line length in characters.

    Raises:
        click.ClickException: If the environment value is not a positive integer.

    Examples:
        os.environ["TOC_MARKDOWN_MAX_LINE_LENGTH"] = "160"
        limit = get_max_line_length(default=120)
    """
    env_value = os.environ.get(MAX_LINE_LENGTH_ENV_VAR)
    if env_value is None:
        return default

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
    """Resolve and validate a Markdown filepath under a base directory.

    Args:
        raw_path: User-supplied path to a Markdown file (absolute or relative).
        base_dir: Working directory that constrains allowed paths.

    Returns:
        Path: Absolute path to the Markdown file.

    Raises:
        click.BadParameter: If the path does not exist, is outside `base_dir`, uses
            an unsupported extension, or traverses a symlink.

    Examples:
        normalize_filepath("docs/README.md", Path.cwd())
        normalize_filepath("~/notes.md", Path.cwd())
    """
    path = Path(raw_path).expanduser()

    if contains_symlink(path):
        error_message = (
            f"Symlinks are not supported for security reasons: {click.style(str(path), fg='red')}"
        )
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
    """Check whether a path or any parent directory is a symlink.

    Args:
        path: Path to inspect.

    Returns:
        bool: True when a symlink is encountered, otherwise False.

    Examples:
        contains_symlink(Path("/tmp/link/child"))
    """
    for candidate in (path, *path.parents):
        try:
            if candidate.is_symlink():
                return True
        except OSError:
            continue
    return False


def collect_file_stat(filepath: Path) -> os.stat_result:
    """Return stat information for a file while disallowing symlinks.

    Args:
        filepath: Path to inspect.

    Returns:
        os.stat_result: File metadata gathered without following symlinks.

    Raises:
        IOError: If the path is inaccessible, a symlink, or not a regular file.

    Examples:
        stat_result = collect_file_stat(Path("README.md"))
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
    """Guard against files that exceed the configured maximum size.

    Args:
        stat_result: File stat used to determine size in bytes.
        max_size: Maximum allowed size in bytes.
        filepath: Path to the file being checked.

    Returns:
        None.

    Raises:
        IOError: If `stat_result.st_size` exceeds `max_size`.

    Examples:
        enforce_file_size(os.stat("README.md"), 102400, Path("README.md"))
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
    """Detect changes between two filesystem snapshots.

    Args:
        expected_stat: Stat captured before processing.
        current_stat: Stat captured after processing.
        filepath: Path to the file being monitored.

    Returns:
        None.

    Raises:
        IOError: If inode, device, size, or modification time differ.

    Examples:
        ensure_file_unchanged(expected_stat, current_stat, filepath)
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
        error_message = f"{click.style(str(filepath), fg='red')} changed during processing; refusing to overwrite."
        raise IOError(error_message)


def safe_read(filepath: Path) -> TextIO:
    """Open a file for reading with consistent error handling.

    Args:
        filepath: Path to the file.

    Returns:
        TextIO: File handle opened for reading in UTF-8.

    Raises:
        IOError: If the path is missing, inaccessible, or not a file.

    Examples:
        with safe_read(Path("README.md")) as handle:
            first_line = handle.readline()
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
        click.ClickException: If configuration is invalid or parsing fails because
            of length limits, header limits, or malformed content.
        IOError: If the file cannot be read or decoded.

    Examples:
        full_file, headers, toc_start, toc_end = parse_file(Path("README.md"), 120, config)
    """
    config = config or TocConfig()
    try:
        validate_config(config)
    except ConfigError as error:
        raise click.ClickException(str(error)) from error

    effective_max_line_length = (
        config.max_line_length if max_line_length is None else max_line_length
    )

    # Read file content
    try:
        with safe_read(filepath) as file:
            content = file.read()
    except UnicodeDecodeError as error:
        error_message = f"Invalid UTF-8 sequence in {filepath}: {click.style(str(error), fg='red')}"
        raise IOError(error_message) from error

    # Parse content using pure function
    try:
        result = parse_markdown(content, effective_max_line_length, config)
    except LineTooLongError as error:
        error_message = (
            f"{click.style(str(filepath), fg='red')} contains a line at line {error.line_number} "
            f"exceeding the maximum allowed length of {click.style(str(error.max_line_length), fg='red')} "
            "characters."
        )
        raise click.ClickException(error_message) from error
    except TooManyHeadersError as error:
        error_message = (
            f"{click.style(str(filepath), fg='red')} contains too many headers "
            f"(limit: {click.style(str(error.limit), fg='red')})."
        )
        raise click.ClickException(error_message) from error
    except ParseError as error:
        error_message = f"{click.style(str(filepath), fg='red')}: {error}"
        raise click.ClickException(error_message) from error

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
    """Rewrite a Markdown file with an updated table of contents.

    Args:
        full_file: Original file content split into lines.
        filepath: Path to the Markdown file to update.
        toc: Rendered TOC lines to insert.
        toc_start_line: Index where the existing TOC starts (0-based).
        toc_end_line: Index where the existing TOC ends (0-based).
        expected_stat: File stat captured after parsing, used to detect races.
        initial_stat: File stat captured before parsing, used to preserve access time.

    Returns:
        None.

    Raises:
        IOError: If the file changes between parsing and writing or cannot be
            updated atomically.

    Examples:
        update_toc(full_file, Path("README.md"), toc_lines, toc_start, toc_end, post_stat, pre_stat)
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
