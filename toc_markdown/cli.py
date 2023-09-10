"""
Generates a table of contents for a markdown file.
If an existing TOC is present, it updates it, otherwise, it inserts a new one.
"""

import re
import string
import sys
import unicodedata
from pathlib import Path

import click

# This pattern matches 2nd and 3rd level headers, but ignores 1st level headers.
HEADER_PATTERN = re.compile(r"^(#{2,3}) (.*)$")


@click.command()
@click.version_option()
@click.argument("filepath", type=click.Path(exists=True, dir_okay=False))
def cli(filepath):
    """
    Generates or updates the table of contents for the specified Markdown file.

    FILEPATH: The path to the Markdown file.

    Example: toc-markdown README.md
    """
    if Path(filepath).suffix.lower() not in [".md", ".markdown"]:
        click.echo(f"Error: {filepath} is not a Markdown file.", err=True)
        sys.exit(1)

    full_file, headers, toc_line_start, toc_line_end = parse_file(filepath)
    toc = generate_toc(headers)

    # Updates TOC
    if toc_line_start is not None and toc_line_end is not None:
        update_toc(full_file, toc, toc_line_start, toc_line_end, filepath)
    # Inserts TOC
    else:
        print("\n".join(toc))


def safe_read(filepath):
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
        click.echo(f"Error accessing {filepath}: {error}", err=True)
        sys.exit(1)


def parse_file(filepath):
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
    full_file = []  # Stores all lines of the file
    headers = []  # Stores all headers found in the file

    # TOC start and end line numbers
    toc_line_start = None
    toc_line_end = None

    # Flag for code blocks
    is_in_code_block = False

    with safe_read(filepath) as file:
        for line_number, line in enumerate(file):
            full_file.append(line)

            # Tracks if we're in a code block
            if line.startswith("```"):
                is_in_code_block = not is_in_code_block
                continue

            # Ignores code blocks and existing TOC
            if is_in_code_block or line.startswith("## Table of Contents"):
                continue

            # Finds headers
            header_match = HEADER_PATTERN.match(line)
            if header_match:
                headers.append(header_match.group(0))

            # Finds TOC start and end line numbers
            if line.startswith("<!-- TOC -->"):
                toc_line_start = line_number
            if line.startswith("<!-- /TOC -->"):
                toc_line_end = line_number

    return full_file, headers, toc_line_start, toc_line_end


def generate_link_from_title(title):
    """
    Generates a link anchor from a given title.

    Args:
        title (str): The title from which to generate the link.

    Returns:
        str: The generated link.
    """
    # Ignores hyphens and underscores
    punctuation = string.punctuation.replace("-", "").replace("_", "")

    link = title.casefold().translate(str.maketrans("", "", punctuation)).strip()
    link = re.sub(r"\s+", "-", link)
    return (
        unicodedata.normalize("NFKD", link)
        .encode("ascii", "ignore")
        .decode("utf-8", "ignore")
    )


def generate_toc(headers):
    """
    Generates a table of contents from a list of headers.

    Args:
        headers (list): A list of markdown headers.

    Returns:
        list: A list of lines that make up the TOC.
    """
    toc = ["## Table of Contents\n"]

    for heading in headers:
        level = heading.count("#")
        title = heading[level:].strip()
        link = generate_link_from_title(title)
        toc.append("    " * (level - 2) + f"1. [{title}](#{link})")

    toc.insert(0, "<!-- TOC -->")
    toc.append("<!-- /TOC -->")

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
