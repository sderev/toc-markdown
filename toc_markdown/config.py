"""Configuration loading and management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

@dataclass
class TocConfig:
    """Configuration for generating Markdown tables of contents.

    Attributes:
        start_marker: Marker inserted before the generated TOC.
        end_marker: Marker inserted after the generated TOC.
        header_text: Heading placed above the TOC.
        min_level: Smallest header level to include.
        max_level: Largest header level to include.
        indent_chars: Characters used to indent nested entries.
        list_style: Bullet style for list items (``"1."``, ``"*"``, or ``"-"``).
        max_file_size: Maximum file size in bytes that will be processed.
        max_line_length: Maximum line length allowed during parsing.
        max_headers: Maximum number of headers that will be included.

    Examples:
        TocConfig(min_level=1, max_level=4, list_style="*")
    """

    # TOC markers
    start_marker: str = "<!-- TOC -->"
    end_marker: str = "<!-- /TOC -->"
    header_text: str = "## Table of Contents"

    # Header levels
    min_level: int = 2
    max_level: int = 3

    # Formatting
    indent_chars: str = "    "
    list_style: str = "1."

    # Limits
    max_file_size: int = 10 * 1024 * 1024
    max_line_length: int = 10_000
    max_headers: int = 10_000


class ConfigError(ValueError):
    """Exception raised when configuration values are invalid.

    Attributes:
        args: Arguments provided to the underlying `ValueError`.

    Examples:
        raise ConfigError("`max_level` must be >= `min_level`")
    """


def load_config(search_path: Path) -> TocConfig:
    """Load configuration from the nearest `pyproject.toml`.

    Walks parent directories from `search_path` to the filesystem root, reading
    the ``[tool.toc-markdown]`` table when present. Returns default values when
    no configuration is found. TOML files that cannot be read or decoded are
    skipped. Raises a `ConfigError` when the table exists but is not a mapping
    or contains unsupported keys.

    Args:
        search_path: Directory used as the starting point for configuration lookup.

    Returns:
        TocConfig: Loaded configuration with defaults applied when necessary.

    Raises:
        ConfigError: If the `[tool.toc-markdown]` table is present but not a mapping or contains unsupported keys.

    Examples:
        load_config(Path("docs"))
    """
    current = search_path.resolve()

    while True:
        config_file = current / "pyproject.toml"

        if config_file.exists():
            try:
                with open(config_file, "rb") as stream:
                    data = tomllib.load(stream)
            except (OSError, tomllib.TOMLDecodeError):
                pass
            else:
                tool_section = data.get("tool", {})

                if "toc-markdown" in tool_section:
                    raw_config = tool_section.get("toc-markdown")

                    if raw_config is None:
                        return TocConfig()

                    if not isinstance(raw_config, dict):
                        raise ConfigError(
                            f"Invalid `[tool.toc-markdown]` settings in {config_file}"
                        )

                    if not raw_config:
                        return TocConfig()

                    try:
                        return TocConfig(**raw_config)
                    except TypeError as error:
                        raise ConfigError(
                            f"Invalid `[tool.toc-markdown]` settings in {config_file}"
                        ) from error

        parent = current.parent
        if parent == current:
            break
        current = parent

    return TocConfig()


def validate_config(config: TocConfig) -> None:
    """Validate a `TocConfig` instance.

    Args:
        config: Configuration to validate.

    Returns:
        None.

    Raises:
        ConfigError: If header levels are inconsistent, required markers or
            formatting fields are empty, list styles are unsupported, or numeric
            limits are non-positive.

    Examples:
        validate_config(TocConfig(min_level=1, max_level=3))
    """

    _ensure_integers(
        {
            "min_level": config.min_level,
            "max_level": config.max_level,
            "max_file_size": config.max_file_size,
            "max_line_length": config.max_line_length,
            "max_headers": config.max_headers,
        }
    )

    if config.min_level < 1:
        raise ConfigError("`min_level` must be >= 1")
    if config.max_level < config.min_level:
        raise ConfigError("`max_level` must be >= `min_level`")
    if config.max_level > 6:
        raise ConfigError("`max_level` must be <= 6")

    if not config.start_marker:
        raise ConfigError("`start_marker` must not be empty")
    if not config.end_marker:
        raise ConfigError("`end_marker` must not be empty")
    if not config.header_text:
        raise ConfigError("`header_text` must not be empty")

    if not config.indent_chars:
        raise ConfigError("`indent_chars` must not be empty")
    if config.list_style not in ("1.", "*", "-"):
        raise ConfigError("`list_style` must be one of: 1., *, -")

    try:
        _ensure_positive(
            {
                "max_file_size": config.max_file_size,
                "max_line_length": config.max_line_length,
                "max_headers": config.max_headers,
            }
        )
    except TypeError as error:
        raise ConfigError("numeric limits must be positive integers") from error


def _ensure_positive(values: dict[str, int]) -> None:
    for key, value in values.items():
        if value <= 0:
            raise ConfigError(f"`{key}` must be a positive integer")


def _ensure_integers(values: dict[str, object]) -> None:
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"`{key}` must be an integer")
