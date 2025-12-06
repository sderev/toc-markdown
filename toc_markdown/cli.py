"""
Generates a table of contents for a markdown file.
If an existing TOC is present, it updates it; otherwise, it outputs it to stdout.
"""

from __future__ import annotations

from pathlib import Path

import click
from .config import ConfigError, build_config
from .filesystem import (
    collect_file_stat,
    enforce_file_size,
    ensure_file_unchanged,
    get_max_file_size,
    get_max_line_length,
    normalize_filepath,
    update_toc,
)
from .generator import generate_toc_entries as generate_toc, validate_toc_markers
from .parser import ParseFileError, parse_file

__all__ = ["cli"]


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
        click.ClickException: If parsing fails due to limits or malformed content,
            or if filesystem safety checks fail.

    Examples:
        toc-markdown README.md --min-level 2 --list-style "-"
    """
    base_dir = Path.cwd().resolve()
    try:
        filepath = normalize_filepath(filepath, base_dir)
    except ValueError as error:
        raise click.BadParameter(str(error)) from error
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

    try:
        max_file_size = get_max_file_size(default=config.max_file_size)
        max_line_length = get_max_line_length(default=config.max_line_length)
    except ValueError as error:
        raise click.ClickException(str(error)) from error

    try:
        initial_stat = collect_file_stat(filepath)
        enforce_file_size(initial_stat, max_file_size, filepath)
    except IOError as error:
        raise click.ClickException(str(error)) from error

    try:
        full_file, headers, toc_start_line, toc_end_line = parse_file(
            filepath, max_line_length, config
        )
    except (ParseFileError, ConfigError) as error:
        raise click.ClickException(str(error)) from error

    try:
        post_parse_stat = collect_file_stat(filepath)
        ensure_file_unchanged(initial_stat, post_parse_stat, filepath)
    except IOError as error:
        raise click.ClickException(str(error)) from error

    toc = generate_toc(headers, config)

    # Updates TOC
    if toc_start_line is not None and toc_end_line is not None:
        try:
            validate_toc_markers(toc_start_line, toc_end_line, config)
        except ValueError as error:
            raise click.BadParameter(str(error)) from error
        try:
            update_toc(
                full_file,
                filepath,
                toc,
                toc_start_line,
                toc_end_line,
                post_parse_stat,
                initial_stat,
                warn=lambda message: click.echo(message, err=True),
            )
        except IOError as error:
            raise click.ClickException(str(error)) from error
    # Inserts TOC
    else:
        print("".join(toc), end="")


if __name__ == "__main__":
    cli()
