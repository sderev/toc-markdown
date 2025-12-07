"""Configuration loading and management."""

from __future__ import annotations

from dataclasses import dataclass, replace
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
        indent_spaces: Number of spaces used for indentation (new schema).
        list_style: Bullet style for list items (``"1."``, ``"*"``, ``"-"``,
            or schema aliases ``"ordered"``/``"unordered"``).
        max_file_size: Maximum file size in bytes that will be processed.
        max_line_length: Maximum line length allowed during parsing.
        max_headers: Maximum number of headers that will be included.
        preserve_unicode: Whether to keep Unicode characters in generated slugs.

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
    indent_spaces: int | None = None
    list_style: str = "1."
    preserve_unicode: bool = False

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
    """Load configuration from the nearest config file.

    Walks parent directories from `search_path` to the filesystem root, reading
    the ``[tool.toc-markdown]`` table from `pyproject.toml` and the
    ``[toc-markdown]`` or ``[tool.toc-markdown]`` table from
    `.toc-markdown.toml` when present. Returns default values when no
    configuration is found. TOML files that cannot be read or decoded are
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
        pyproject_config = _load_from_file(
            current / "pyproject.toml", table_paths=[("tool", "toc-markdown")]
        )
        if pyproject_config is not None:
            return normalize_config(pyproject_config)

        dotfile_config = _load_from_file(
            current / ".toc-markdown.toml",
            table_paths=[("toc-markdown",), ("tool", "toc-markdown")],
        )
        if dotfile_config is not None:
            return normalize_config(dotfile_config)

        parent = current.parent
        if parent == current:
            break
        current = parent

    return TocConfig()


_MISSING = object()


def _load_from_file(config_file: Path, table_paths: list[tuple[str, ...]]) -> TocConfig | None:
    if not config_file.exists():
        return None

    try:
        with open(config_file, "rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError):
        return None

    for table_path in table_paths:
        raw_config = _extract_table(data, table_path)
        if raw_config is _MISSING:
            continue
        return _build_config_from_raw(raw_config, config_file, table_path)

    return None


def _extract_table(data: object, table_path: tuple[str, ...]) -> object:
    current = data
    for key in table_path:
        if not isinstance(current, dict) or key not in current:
            return _MISSING
        current = current[key]
    return current


def _build_config_from_raw(
    raw_config: object, config_file: Path, table_path: tuple[str, ...]
) -> TocConfig:
    table_display = ".".join(table_path)

    if raw_config is None:
        return TocConfig()

    if not isinstance(raw_config, dict):
        raise ConfigError(f"Invalid `[{table_display}]` settings in {config_file}")

    if not raw_config:
        return TocConfig()

    try:
        return TocConfig(**raw_config)
    except TypeError as error:
        raise ConfigError(f"Invalid `[{table_display}]` settings in {config_file}") from error


def normalize_config(config: TocConfig) -> TocConfig:
    indent_chars = config.indent_chars
    if config.indent_spaces is not None:
        _ensure_integers({"indent_spaces": config.indent_spaces})
        if config.indent_spaces <= 0:
            raise ConfigError("`indent_spaces` must be a positive integer")
        indent_chars = " " * config.indent_spaces

    list_style = config.list_style
    if list_style == "ordered":
        list_style = "1."
    elif list_style == "unordered":
        list_style = "-"

    return replace(config, indent_chars=indent_chars, list_style=list_style)


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
    config = normalize_config(config)

    _ensure_integers(
        {
            "min_level": config.min_level,
            "max_level": config.max_level,
            "max_file_size": config.max_file_size,
            "max_line_length": config.max_line_length,
            "max_headers": config.max_headers,
            **({"indent_spaces": config.indent_spaces} if config.indent_spaces is not None else {}),
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
        raise ConfigError("`list_style` must be one of: 1., *, -, ordered, unordered")
    if not isinstance(config.preserve_unicode, bool):
        raise ConfigError("`preserve_unicode` must be a boolean")

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
    if "indent_chars" in changes and "indent_spaces" not in changes:
        changes["indent_spaces"] = None
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
    config = normalize_config(config)
    validate_config(config)
    return config


def _ensure_positive(values: dict[str, int]) -> None:
    for key, value in values.items():
        if value <= 0:
            raise ConfigError(f"`{key}` must be a positive integer")


def _ensure_integers(values: dict[str, object]) -> None:
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"`{key}` must be an integer")
