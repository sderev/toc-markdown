"""
Generates a table of contents for a markdown file.
If an existing TOC is present, it updates it, otherwise, it inserts a new one.
"""

import os
import re
import string
import unicodedata
from pathlib import Path
from typing import TextIO

import click

# This pattern matches 2nd and 3rd level headers, but ignores 1st level headers.
HEADER_PATTERN = re.compile(r"^(#{2,3}) (.*)$")

TOC_START_MARKER = "<!-- TOC -->"
TOC_END_MARKER = "<!-- /TOC -->"
MARKDOWN_EXTENSIONS = (".md", ".markdown")
CODE_FENCE = "```"
TOC_HEADER = "## Table of Contents"


@click.command()
@click.version_option()
@click.argument("filepath", type=click.Path(exists=True, dir_okay=False))
def cli(filepath: str):
    """
    Generates or updates the table of contents for the specified Markdown file.

    FILEPATH: The path to the Markdown file.

    Example: toc-markdown README.md
    """
    filepath = Path(filepath).resolve()

    if filepath.suffix.lower() not in MARKDOWN_EXTENSIONS:
        error_message = f"{click.style(f'{filepath} is not a Markdown file.', fg='red')}\n"
        error_message += f"Supported extensions are: {', '.join(MARKDOWN_EXTENSIONS)}"
        raise click.BadParameter(error_message)

    full_file, headers, toc_start_line, toc_end_line = parse_file(filepath)
    toc = generate_toc(headers)

    # Updates TOC
    if toc_start_line is not None and toc_end_line is not None:
        update_toc(full_file, toc, toc_start_line, toc_end_line, filepath)
    # Inserts TOC
    else:
        print("\n".join(toc))


def safe_read(filepath: Path) -> TextIO:
    """
    Opens a file and handles any errors.

    Args:
        filepath (str): The path to the file.
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


def parse_file(filepath: Path) -> tuple[list[str], list[str], int | None, int | None]:
    """
    Parses the specified Markdown file.

    Args:
        filepath (str): The path to the markdown file.

    Returns:
        tuple: A tuple containing:
            full_file (list): A list of all lines in the file.
            headers (list): A list of all headers in the file.
            toc_line_start (int): The line number where the TOC starts.
            toc_line_end (int): The line number where the TOC ends.
    """
    full_file: list[str] = []
    headers: list[str] = []

    # TOC start and end line numbers
    toc_start_line: int | None = None
    toc_end_line: int | None = None

    # Flag for code blocks
    is_in_code_block = False

    with safe_read(filepath) as file:
        for line_number, line in enumerate(file):
            full_file.append(line)

            # Tracks if we're in a code block
            if line.startswith(CODE_FENCE):
                is_in_code_block = not is_in_code_block
                continue

            # Ignores code blocks and existing TOC
            if is_in_code_block or line.startswith(TOC_HEADER):
                continue

            # Finds headers
            header_match = HEADER_PATTERN.match(line)
            if header_match:
                headers.append(header_match.group(0))

            # Finds TOC start and end line numbers
            if line.startswith(TOC_START_MARKER):
                toc_start_line = line_number
            if line.startswith(TOC_END_MARKER):
                toc_end_line = line_number

    return full_file, headers, toc_start_line, toc_end_line


def generate_slug(title: str) -> str:
    """
    Generates a slug for a given title to be used as an anchor link in markdown.

    Args:
        title (str): The title to generate a slug for.

    Returns:
        str: The generated link.
    """
    # Keep hyphens and underscores in the slug, but remove other punctuation
    punctuation = string.punctuation.replace("-", "").replace("_", "")
    slug = title.casefold().translate(str.maketrans("", "", punctuation)).strip()

    slug = re.sub(r"\s+", "-", slug)
    slug = unicodedata.normalize("NFKD", slug).encode("ascii", "ignore").decode("utf-8", "ignore")
    slug = slug.strip("-")

    return slug if slug else "untitled"


def generate_toc(headers: list[str]) -> list[str]:
    """
    Generates a table of contents from a list of headers.

    Args:
        headers (list): A list of markdown headers.

    Returns:
        list: A list of lines that make up the TOC.
    """
    toc = [f"{TOC_START_MARKER}", "## Table of Contents\n"]

    for heading in headers:
        level = heading.count("#")
        title = heading[level:].strip()
        link = generate_slug(title)
        toc.append("    " * (level - 2) + f"1. [{title}](#{link})")

    toc.append(f"{TOC_END_MARKER}")

    return toc


def update_toc(full_file, toc, toc_line_start, toc_line_end, filepath):
    """
    Updates the existing TOC with the new one.

    Args:
        full_file (list): A list of all lines in the file.
        toc (list): A list of lines that make up the TOC.
        toc_start (int): The line number where the TOC starts.
        toc_end (int): The line number where the TOC ends.
        filepath (str): The path to the file.
    """
    with open(filepath, "w", encoding="UTF-8") as file:
        file.writelines(full_file[:toc_line_start])
        for line in toc:
            file.write(line + "\n")
        file.writelines(full_file[toc_line_end + 1 :])


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
