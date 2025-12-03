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
