from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from toc_markdown.config import (
    MAX_CONFIGURED_FILE_SIZE,
    ConfigError,
    TocConfig,
    load_config,
    validate_config,
)


def _write_pyproject(base: Path, body: str) -> Path:
    path = base / "pyproject.toml"
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


def _write_toc_markdown(base: Path, body: str) -> Path:
    path = base / ".toc-markdown.toml"
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


def test_loads_config_from_pyproject(tmp_path: Path):
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        start_marker = "<!-- CUSTOM -->"
        end_marker = "<!-- /CUSTOM -->"
        header_text = "# Contents"
        min_level = 1
        max_level = 4
        indent_chars = "\\t"
        list_style = "*"
        max_file_size = 1
        max_line_length = 2
        max_headers = 3
        """,
    )

    config = load_config(tmp_path)

    assert config == TocConfig(
        start_marker="<!-- CUSTOM -->",
        end_marker="<!-- /CUSTOM -->",
        header_text="# Contents",
        min_level=1,
        max_level=4,
        indent_chars="\t",
        list_style="*",
        max_file_size=1,
        max_line_length=2,
        max_headers=3,
    )


def test_loads_config_from_dotfile(tmp_path: Path):
    _write_toc_markdown(
        tmp_path,
        """
        [toc-markdown]
        start_marker = "<!-- DOT -->"
        header_text = "# Dotfile"
        """,
    )
    nested = tmp_path / "child"
    nested.mkdir()

    config = load_config(nested)

    assert config.start_marker == "<!-- DOT -->"
    assert config.header_text == "# Dotfile"


def test_load_config_walks_up_directories(tmp_path: Path):
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        start_marker = "<!-- ROOT -->"
        """,
    )
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)

    config = load_config(nested)

    assert config.start_marker == "<!-- ROOT -->"


def test_empty_config_table_stops_inheritance(tmp_path: Path):
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        start_marker = "<!-- ROOT -->"
        """,
    )
    child = tmp_path / "child"
    child.mkdir()
    _write_pyproject(
        child,
        """
        [tool.toc-markdown]
        """,
    )

    config = load_config(child)

    assert config.start_marker == TocConfig().start_marker


def test_load_config_returns_defaults_when_missing(tmp_path: Path):
    config = load_config(tmp_path)

    assert config == TocConfig()


def test_load_config_skips_invalid_toml(tmp_path: Path):
    invalid_dir = tmp_path / "invalid"
    invalid_dir.mkdir()
    _write_pyproject(invalid_dir, "not = {valid")
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        header_text = "## From Parent"
        """,
    )

    nested = invalid_dir / "child"
    nested.mkdir()
    config = load_config(nested)

    assert config.header_text == "## From Parent"


def test_load_config_errors_on_invalid_table(tmp_path: Path):
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        start_marker = "<!-- OK -->"
        unexpected = true
        """,
    )

    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_partial_config_merges_with_defaults(tmp_path: Path):
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        list_style = "-"
        max_headers = 500
        """,
    )

    config = load_config(tmp_path)

    assert config.list_style == "-"
    assert config.max_headers == 500
    # Defaults preserved
    defaults = TocConfig()
    assert config.start_marker == defaults.start_marker
    assert config.indent_chars == defaults.indent_chars


def test_indent_spaces_sets_indent_chars(tmp_path: Path):
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        indent_spaces = 2
        list_style = "unordered"
        """,
    )

    config = load_config(tmp_path)

    assert config.indent_spaces == 2
    assert config.indent_chars == "  "
    assert config.list_style == "-"


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        ("ordered", "1."),
        ("unordered", "-"),
    ],
)
def test_list_style_accepts_schema_aliases(tmp_path: Path, style: str, expected: str):
    _write_pyproject(
        tmp_path,
        f"""
        [tool.toc-markdown]
        list_style = "{style}"
        """,
    )

    config = load_config(tmp_path)

    assert config.list_style == expected


@pytest.mark.parametrize(
    "config",
    [
        TocConfig(min_level=0),
        TocConfig(min_level=3, max_level=2),
        TocConfig(max_level=7),
        TocConfig(start_marker=""),
        TocConfig(end_marker=""),
        TocConfig(header_text=""),
        TocConfig(indent_chars=""),
        TocConfig(list_style="?"),
        TocConfig(max_file_size=0),
        TocConfig(max_file_size=MAX_CONFIGURED_FILE_SIZE + 1),
        TocConfig(max_line_length=-1),
        TocConfig(max_headers=0),
    ],
)
def test_validate_config_rejects_invalid_values(config: TocConfig):
    with pytest.raises(ConfigError):
        validate_config(config)


@pytest.mark.parametrize(
    "config",
    [
        TocConfig(max_file_size="big"),  # type: ignore[arg-type]
        TocConfig(max_line_length="long"),  # type: ignore[arg-type]
        TocConfig(max_headers="many"),  # type: ignore[arg-type]
        TocConfig(min_level="2"),  # type: ignore[arg-type]
        TocConfig(max_level="3"),  # type: ignore[arg-type]
    ],
)
def test_validate_config_rejects_non_numeric_limits(config: TocConfig):
    with pytest.raises(ConfigError):
        validate_config(config)


def test_load_config_handles_non_dict_table(tmp_path: Path):
    """Test that config loading errors when table is not a dict (line 154)."""
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        start_marker = "test"
        """,
    )
    # Write a pyproject.toml with non-dict table by directly writing invalid TOML structure
    # Actually, we need to create a case where raw_config is not a dict
    # This happens when the table exists but is not a mapping (e.g., an array or scalar)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        'tool = { toc-markdown = "not-a-dict" }\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match=r"Invalid `\[tool\.toc-markdown\]` settings"):
        load_config(tmp_path)


def test_load_config_handles_null_table(tmp_path: Path):
    """Test that config loading returns defaults when table is null (line 151)."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[tool.toc-markdown]\n",
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config == TocConfig()


def test_load_config_skips_missing_table(tmp_path: Path):
    """Test that config loading skips when table is missing (lines 130, 133, 140)."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[other-section]\nkey = "value"\n',
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config == TocConfig()


def test_validate_config_rejects_non_bool_preserve_unicode():
    """Test that validate_config errors when preserve_unicode is not a bool (line 231)."""
    config = TocConfig(preserve_unicode="yes")  # type: ignore[arg-type]

    with pytest.raises(ConfigError, match="`preserve_unicode` must be a boolean"):
        validate_config(config)


def test_validate_config_rejects_zero_indent_spaces(tmp_path: Path):
    """Test that validate_config errors when indent_spaces is zero or negative (line 170)."""
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        indent_spaces = 0
        """,
    )

    with pytest.raises(ConfigError, match="`indent_spaces` must be a positive integer"):
        load_config(tmp_path)


def test_validate_config_rejects_negative_indent_spaces(tmp_path: Path):
    """Test that validate_config errors when indent_spaces is negative (line 170)."""
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        indent_spaces = -1
        """,
    )

    with pytest.raises(ConfigError, match="`indent_spaces` must be a positive integer"):
        load_config(tmp_path)


def test_validate_config_rejects_non_integer_indent_spaces(tmp_path: Path):
    """Test that validate_config errors when indent_spaces is not an integer."""
    _write_pyproject(
        tmp_path,
        """
        [tool.toc-markdown]
        indent_spaces = "four"
        """,
    )

    with pytest.raises(ConfigError, match="`indent_spaces` must be an integer"):
        load_config(tmp_path)
