from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from toc_markdown.config import ConfigError, TocConfig, load_config


def _write_pyproject(base: Path, body: str) -> Path:
    path = base / "pyproject.toml"
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
