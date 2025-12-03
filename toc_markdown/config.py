"""Configuration loading and management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

@dataclass
class TocConfig:
    """Configuration for TOC generation."""

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
    """Raised when configuration values are invalid."""


def load_config(search_path: Path) -> TocConfig:
    """
    Load configuration from pyproject.toml, walking parents until root.

    Returns default values when no configuration is found.

    Example:
        >>> load_config(Path("docs")).start_marker
        '<!-- TOC -->'
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
    """Validate configuration values."""

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
