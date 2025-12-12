"""Filesystem helpers for toc-markdown."""

from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from .constants import DEFAULT_MAX_FILE_SIZE, DEFAULT_MAX_LINE_LENGTH, MARKDOWN_EXTENSIONS

MAX_FILE_SIZE_ENV_VAR = "TOC_MARKDOWN_MAX_FILE_SIZE"
MAX_LINE_LENGTH_ENV_VAR = "TOC_MARKDOWN_MAX_LINE_LENGTH"


def get_max_file_size(default: int = DEFAULT_MAX_FILE_SIZE) -> int:
    """Resolve the maximum allowed file size.

    Args:
        default: Fallback value in bytes when the environment variable is unset.

    Returns:
        int: Maximum allowed file size in bytes.

    Raises:
        ValueError: If the environment value is not a positive integer.

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
            f"Invalid value for {MAX_FILE_SIZE_ENV_VAR}: {env_value} (expected positive integer)"
        )
        raise ValueError(error_message) from error

    if max_size <= 0:
        error_message = f"{MAX_FILE_SIZE_ENV_VAR} must be a positive integer, got {max_size}."
        raise ValueError(error_message)

    return max_size


def get_max_line_length(default: int = DEFAULT_MAX_LINE_LENGTH) -> int:
    """Resolve the maximum allowed line length.

    Args:
        default: Fallback value in characters when the environment variable is
            unset.

    Returns:
        int: Maximum allowed line length in characters.

    Raises:
        ValueError: If the environment value is not a positive integer.

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
            f"Invalid value for {MAX_LINE_LENGTH_ENV_VAR}: {env_value} (expected positive integer)"
        )
        raise ValueError(error_message) from error

    if max_length <= 0:
        error_message = f"{MAX_LINE_LENGTH_ENV_VAR} must be a positive integer, got {max_length}."
        raise ValueError(error_message)

    return max_length


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


def normalize_filepath(raw_path: str, base_dir: Path) -> Path:
    """Resolve and validate a Markdown filepath under a base directory.

    Args:
        raw_path: User-supplied path to a Markdown file (absolute or relative).
        base_dir: Working directory that constrains allowed paths.

    Returns:
        Path: Absolute path to the Markdown file.

    Raises:
        ValueError: If the path does not exist, is outside `base_dir`, uses an
            unsupported extension, or traverses a symlink.

    Examples:
        normalize_filepath("docs/README.md", Path.cwd())
        normalize_filepath("~/notes.md", Path.cwd())
    """
    path = Path(raw_path).expanduser()

    if contains_symlink(path):
        error_message = f"Symlinks are not supported for security reasons: {path}"
        raise ValueError(error_message)

    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as error:
        error_message = f"{path} does not exist."
        raise ValueError(error_message) from error
    except OSError as error:
        error_message = f"Error resolving {path}: {error}"
        raise ValueError(error_message) from error

    if not resolved.is_file():
        error_message = f"{resolved} is not a regular file."
        raise ValueError(error_message)

    try:
        resolved.relative_to(base_dir)
    except ValueError as error:
        error_message = f"{resolved} is outside of the working directory {base_dir}."
        raise ValueError(error_message) from error

    if resolved.suffix.lower() not in MARKDOWN_EXTENSIONS:
        error_message = f"{resolved} is not a Markdown file.\n"
        error_message += f"Supported extensions are: {', '.join(MARKDOWN_EXTENSIONS)}"
        raise ValueError(error_message)

    return resolved


def collect_file_stat(filepath: Path) -> os.stat_result:
    """Return stat information for a file while disallowing symlinks.

    Args:
        filepath: Path to the file.

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
        error_message = f"Error accessing {filepath}: {error}"
        raise IOError(error_message) from error

    if stat.S_ISLNK(stat_result.st_mode):
        error_message = f"Symlinks are not supported: {filepath}."
        raise IOError(error_message)

    if not stat.S_ISREG(stat_result.st_mode):
        error_message = f"{filepath} is not a regular file."
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
        error_message = f"{filepath} exceeds the maximum allowed size of {max_size} bytes."
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
        error_message = f"{filepath} changed during processing; refusing to overwrite."
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
        error_message = f"Error accessing {filepath}: {error}"
        raise IOError(error_message) from error


def update_toc(
    full_file: list[str],
    filepath: Path,
    toc: list[str],
    toc_start_line: int,
    toc_end_line: int,
    expected_stat: os.stat_result,
    initial_stat: os.stat_result,
    warn: Callable[[str], None] | None = None,
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
        warn: Optional callback for emitting non-fatal warnings (e.g., ownership preservation).

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

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="UTF-8", delete=False, dir=filepath.parent
        ) as tmp_file:
            temp_path = Path(tmp_file.name)
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
                    if warn is not None:
                        warn(
                            f"Warning: Could not preserve file ownership for {filepath.name} "
                            "(requires elevated privileges)"
                        )

        # Replace the original file with the temporary file (atomic operation)
        os.replace(temp_path, filepath)

        # Preserve access time (mtime intentionally NOT preserved to reflect actual modification)
        # We read the new mtime from the replaced file and restore only the original atime
        current_stat = filepath.stat()
        os.utime(filepath, ns=(atime_ns, current_stat.st_mtime_ns))
    finally:
        if temp_path is not None:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except OSError:
                pass
